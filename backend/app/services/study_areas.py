import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import geopandas as gpd
import numpy as np
import requests
import shapely
from shapely.geometry import Point


class BoundaryDataError(RuntimeError):
    """Raised when a sourced study boundary or city reference point is invalid."""


@dataclass(frozen=True)
class StudyArea:
    region_id: str
    name: str
    resolution_m: int
    geometry: Any
    boundary_type: str
    source: str
    source_reference: str
    license: str
    metadata: dict[str, Any]


CITY_REFERENCES = (
    ("chennai", "Chennai", "R1766358", 15_000),
    ("coimbatore", "Coimbatore", "N245589078", 15_000),
    ("madurai", "Madurai", "R11268397", 15_000),
)
GEOGRAPHIC_BOUNDARY_API = "https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/"
BOUNDARY_FILENAME = "geoBoundaries-IND-ADM1_simplified.geojson"
NOMINATIM_LOOKUP_URL = "https://nominatim.openstreetmap.org/lookup"
NOMINATIM_USER_AGENT = "ECOTHERM urban heat research demo (local application)"


def load_study_areas(
    cache_dir: Path,
    *,
    refresh_boundaries: bool = False,
) -> tuple[dict[str, StudyArea], dict[str, Any]]:
    boundary_cache = cache_dir / "raw" / "boundaries"
    boundary_cache.mkdir(parents=True, exist_ok=True)
    boundary_path = boundary_cache / BOUNDARY_FILENAME
    boundary_metadata = _load_boundary_metadata(boundary_path, refresh_boundaries)
    state_geometry = _load_tamil_nadu_geometry(boundary_path)

    areas: dict[str, StudyArea] = {
        "tamil_nadu": StudyArea(
            region_id="tamil_nadu",
            name="Tamil Nadu",
            resolution_m=1000,
            geometry=state_geometry,
            boundary_type="administrative_boundary",
            source=boundary_metadata["boundarySource"],
            source_reference=boundary_metadata["gjDownloadURL"],
            license=boundary_metadata["boundaryLicense"],
            metadata={
                "boundary_id": boundary_metadata["boundaryID"],
                "boundary_year": boundary_metadata["boundaryYearRepresented"],
                "source_data_update_date": boundary_metadata["sourceDataUpdateDate"],
                "geometry_source": "simplified geoBoundaries open boundary",
            },
        )
    }

    for location_id, name, osm_id, radius_m in CITY_REFERENCES:
        district_boundary = _load_cached_district_boundary(
            boundary_cache,
            name,
        )
        if district_boundary is not None:
            geometry, district_source, district_reference, district_license, district_metadata = district_boundary
            areas[location_id] = StudyArea(
                region_id=location_id,
                name=name,
                resolution_m=100,
                geometry=geometry,
                boundary_type="administrative_district_boundary",
                source=district_source,
                source_reference=district_reference,
                license=district_license,
                metadata={
                    "district_name": name,
                    "district_boundary_year": district_metadata["boundary_year"],
                    "extent_note": (
                        "Real cached ADM2 district boundary. This replaces the "
                        "previous circular city study extent; it is a district "
                        "boundary, not a municipal ward or city-corporation boundary."
                    ),
                    "ward_boundary_status": "not_available_grid_fallback",
                    "analysis_unit": "100 m grid cell; district fallback, not a municipal ward",
                },
            )
            continue

        point_payload = _load_city_reference(boundary_cache, osm_id)
        longitude = float(point_payload["lon"])
        latitude = float(point_payload["lat"])
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise BoundaryDataError(f"Invalid OpenStreetMap coordinates for {name}.")
        center = gpd.GeoSeries([Point(longitude, latitude)], crs="EPSG:4326")
        projected_center = center.to_crs("EPSG:32644").iloc[0]
        study_geometry = (
            gpd.GeoSeries([projected_center.buffer(radius_m)], crs="EPSG:32644")
            .to_crs("EPSG:4326")
            .iloc[0]
        )
        areas[location_id] = StudyArea(
            region_id=location_id,
            name=name,
            resolution_m=100,
            geometry=study_geometry,
            boundary_type="circular_city_study_extent",
            source="OpenStreetMap city/place reference point via Nominatim",
            source_reference=(
                f"https://www.openstreetmap.org/{osm_id[0].lower()}/"
                f"{osm_id[1:]}"
            ),
            license=point_payload.get(
                "licence",
                "Open Database License 1.0 (ODbL); OpenStreetMap contributors",
            ),
            metadata={
                "center_latitude": latitude,
                "center_longitude": longitude,
                "center_osm_id": osm_id,
                "radius_m": radius_m,
                "extent_note": (
                    "Circular analytical study extent around the sourced city "
                    "reference point; not a municipal boundary."
                ),
                "ward_boundary_status": "not_available_grid_fallback",
                "analysis_unit": "100 m grid cell; not a municipal ward",
            },
        )

    output_dir = cache_dir / "processed" / "boundaries"
    output_dir.mkdir(parents=True, exist_ok=True)
    regions = gpd.GeoDataFrame(
        [
            {
                "region_id": area.region_id,
                "name": area.name,
                "resolution_m": area.resolution_m,
                "boundary_type": area.boundary_type,
                "source": area.source,
                "source_reference": area.source_reference,
                "license": area.license,
                **area.metadata,
                "geometry": area.geometry,
            }
            for area in areas.values()
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )
    regions.to_file(output_dir / "regions.geojson", driver="GeoJSON")
    manifest = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "state_boundary": boundary_metadata,
        "city_reference_provider": "OpenStreetMap Nominatim",
        "city_boundary_license": (
            "Open Database License 1.0 (ODbL); OpenStreetMap contributors"
        ),
        "regions": [
            {
                "region_id": area.region_id,
                "name": area.name,
                "boundary_type": area.boundary_type,
                "resolution_m": area.resolution_m,
                "source": area.source,
                "source_reference": area.source_reference,
                "license": area.license,
                **area.metadata,
            }
            for area in areas.values()
        ],
    }
    (output_dir / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return areas, manifest


def _load_cached_district_boundary(
    boundary_cache: Path,
    district_name: str,
) -> tuple[Any, str, str, str, dict[str, str]] | None:
    cache_root = boundary_cache.parent.parent
    district_path = cache_root / "processed" / "boundaries" / "districts.geojson"
    manifest_path = (
        cache_root / "processed" / "boundaries" / "districts_manifest.json"
    )
    if not district_path.is_file() or not manifest_path.is_file():
        return None
    try:
        districts = gpd.read_file(district_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if districts.crs is None or "district_name" not in districts.columns:
        return None
    matches = districts[districts["district_name"].astype(str).str.casefold() == district_name.casefold()]
    if len(matches) != 1:
        return None
    district = matches.iloc[0]
    geometry = district.geometry
    if geometry is None or geometry.is_empty:
        return None
    source = str(district.get("source") or manifest.get("boundary_source") or "")
    source_reference = str(district.get("source_reference") or "")
    license_name = str(district.get("license") or manifest.get("boundary_license") or "")
    metadata = {
        "boundary_year": str(district.get("boundary_year") or manifest.get("boundary_year") or ""),
    }
    if not source or not source_reference or not license_name:
        return None
    return geometry, source, source_reference, license_name, metadata


def load_districts(
    cache_dir: Path,
    state_area: StudyArea,
    *,
    refresh: bool = False,
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    boundary_cache = cache_dir / "raw" / "boundaries"
    boundary_cache.mkdir(parents=True, exist_ok=True)
    metadata_path = boundary_cache / "geoBoundaries-IND-ADM2-metadata.json"
    geometry_path = boundary_cache / "geoBoundaries-IND-ADM2_simplified.geojson"
    try:
        if refresh or not metadata_path.is_file():
            response = requests.get(
                "https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/",
                timeout=60,
            )
            response.raise_for_status()
            metadata = response.json()
            metadata_path.write_text(
                json.dumps(metadata, indent=2),
                encoding="utf-8",
            )
        else:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    except (requests.RequestException, OSError, ValueError) as exc:
        raise BoundaryDataError(
            f"Could not retrieve geoBoundaries district metadata: {exc}"
        ) from exc
    for field in (
        "boundaryID",
        "boundaryYearRepresented",
        "boundarySource",
        "boundaryLicense",
    ):
        if not metadata.get(field):
            raise BoundaryDataError(
                "geoBoundaries district metadata omitted required provenance."
            )
    if refresh or not _is_feature_collection(geometry_path):
        download_url = metadata["simplifiedGeometryGeoJSON"].replace(
            "https://github.com/wmgeolab/geoBoundaries/raw/",
            "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/",
            1,
        )
        try:
            response = requests.get(download_url, timeout=120)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
                raise BoundaryDataError(
                    "geoBoundaries returned a non-GeoJSON district dataset."
                )
            temporary_path = geometry_path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            temporary_path.replace(geometry_path)
        except (requests.RequestException, OSError, ValueError) as exc:
            raise BoundaryDataError(
                f"Could not download geoBoundaries district GeoJSON: {exc}"
            ) from exc

    try:
        districts = gpd.read_file(geometry_path)
    except (OSError, ValueError) as exc:
        raise BoundaryDataError(
            f"Could not read the cached district dataset: {exc}"
        ) from exc
    if districts.crs is None or "shapeName" not in districts.columns:
        raise BoundaryDataError("District dataset is missing its CRS or district names.")
    projected = districts.to_crs("EPSG:32644")
    projected["geometry"] = projected.geometry.map(
        lambda geometry: geometry if geometry.is_valid else shapely.make_valid(geometry)
    )
    projected_state = (
        gpd.GeoSeries([state_area.geometry], crs="EPSG:4326")
        .to_crs("EPSG:32644")
        .iloc[0]
    )
    intersection_area = projected.geometry.intersection(projected_state).area
    area_fraction = intersection_area / projected.geometry.area.replace(0, np.nan)
    selected = projected[area_fraction >= 0.5].copy()
    if selected.empty:
        raise BoundaryDataError(
            "No district polygons substantially intersect the Tamil Nadu boundary."
        )
    selected["geometry"] = selected.geometry.intersection(projected_state)
    selected = selected[selected.geometry.notna() & ~selected.geometry.is_empty]
    selected["district_name"] = selected["shapeName"].astype(str)
    selected["district_id"] = selected["district_name"].map(
        lambda name: re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    )
    selected["source"] = metadata["boundarySource"]
    selected["source_reference"] = metadata["gjDownloadURL"]
    selected["license"] = metadata["boundaryLicense"]
    selected["boundary_year"] = metadata["boundaryYearRepresented"]
    output = selected[
        [
            "district_id",
            "district_name",
            "source",
            "source_reference",
            "license",
            "boundary_year",
            "geometry",
        ]
    ].to_crs("EPSG:4326")
    if output["district_id"].duplicated().any():
        raise BoundaryDataError("District names do not form unique district identifiers.")
    manifest = {
        "boundary_id": metadata["boundaryID"],
        "boundary_type": metadata["boundaryType"],
        "boundary_year": metadata["boundaryYearRepresented"],
        "boundary_source": metadata["boundarySource"],
        "boundary_license": metadata["boundaryLicense"],
        "district_count": len(output),
        "selection_rule": "district polygons with at least 50% area inside Tamil Nadu ADM1",
    }
    output_dir = cache_dir / "processed" / "boundaries"
    output_dir.mkdir(parents=True, exist_ok=True)
    output.to_file(output_dir / "districts.geojson", driver="GeoJSON")
    (output_dir / "districts_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return output, manifest


def _load_boundary_metadata(boundary_path: Path, refresh: bool) -> dict[str, Any]:
    api_metadata_path = boundary_path.with_name("geoBoundaries-IND-ADM1-metadata.json")
    try:
        if refresh or not api_metadata_path.exists():
            response = requests.get(GEOGRAPHIC_BOUNDARY_API, timeout=60)
            response.raise_for_status()
            metadata = response.json()
            api_metadata_path.write_text(
                json.dumps(metadata, indent=2),
                encoding="utf-8",
            )
        else:
            metadata = json.loads(api_metadata_path.read_text(encoding="utf-8-sig"))
    except (requests.RequestException, OSError, ValueError) as exc:
        raise BoundaryDataError(
            f"Could not retrieve geoBoundaries metadata: {exc}"
        ) from exc

    required = (
        "boundaryID",
        "boundaryYearRepresented",
        "boundarySource",
        "boundaryLicense",
        "gjDownloadURL",
    )
    if any(not metadata.get(field) for field in required):
        raise BoundaryDataError("geoBoundaries metadata omitted required provenance.")
    if refresh or not _is_feature_collection(boundary_path):
        download_url = metadata.get("simplifiedGeometryGeoJSON")
        if not download_url:
            download_url = metadata["gjDownloadURL"]
        parsed = urlparse(download_url)
        if parsed.netloc == "github.com" and "/raw/" in parsed.path:
            download_url = download_url.replace(
                "https://github.com/wmgeolab/geoBoundaries/raw/",
                "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/",
                1,
            )
        try:
            response = requests.get(download_url, timeout=120)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
                raise BoundaryDataError("geoBoundaries returned a non-GeoJSON boundary.")
            temporary_path = boundary_path.with_suffix(".tmp")
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            temporary_path.replace(boundary_path)
        except (requests.RequestException, OSError, ValueError) as exc:
            raise BoundaryDataError(
                f"Could not download the geoBoundaries GeoJSON: {exc}"
            ) from exc
    return metadata


def _is_feature_collection(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("type") == "FeatureCollection"
        and isinstance(payload.get("features"), list)
    )


def _load_tamil_nadu_geometry(boundary_path: Path) -> Any:
    try:
        boundaries = gpd.read_file(boundary_path)
    except (OSError, ValueError) as exc:
        raise BoundaryDataError(
            f"Could not read the cached geoBoundaries file: {exc}"
        ) from exc
    if boundaries.crs is None:
        raise BoundaryDataError("geoBoundaries file does not declare a CRS.")
    name_field = next(
        (
            field
            for field in ("shapeName", "shapeNameEN", "shapeNameAlt")
            if field in boundaries.columns
        ),
        None,
    )
    if name_field is None:
        raise BoundaryDataError("geoBoundaries features have no recognized name field.")
    selected = boundaries[
        boundaries[name_field].astype(str).str.contains("Tamil", case=False, regex=False)
    ]
    if len(selected) != 1:
        raise BoundaryDataError(
            f"Expected one Tamil Nadu state geometry, found {len(selected)}."
        )
    geometry = selected.to_crs("EPSG:4326").geometry.iloc[0]
    if geometry.is_empty:
        raise BoundaryDataError("Tamil Nadu boundary geometry is empty.")
    if not geometry.is_valid:
        geometry = shapely.make_valid(geometry)
    if geometry.geom_type not in ("Polygon", "MultiPolygon"):
        raise BoundaryDataError(
            f"Tamil Nadu boundary has unsupported geometry type {geometry.geom_type}."
        )
    return geometry


def _load_city_reference(boundary_cache: Path, osm_id: str) -> dict[str, Any]:
    cache_path = boundary_cache / f"nominatim_{osm_id}.json"
    if cache_path.is_file():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BoundaryDataError(
                f"Cached city reference {cache_path.name} is invalid."
            ) from exc
        return _first_reference(payload, osm_id)

    if list(boundary_cache.glob("nominatim_*.json")):
        time.sleep(1.1)
    response = requests.get(
        NOMINATIM_LOOKUP_URL,
        params={
            "osm_ids": osm_id,
            "format": "jsonv2",
            "addressdetails": 1,
        },
        headers={"User-Agent": NOMINATIM_USER_AGENT},
        timeout=60,
    )
    try:
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise BoundaryDataError(
            f"Could not resolve OpenStreetMap city reference {osm_id}: {exc}"
        ) from exc
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return _first_reference(payload, osm_id)


def _first_reference(payload: Any, osm_id: str) -> dict[str, Any]:
    if not isinstance(payload, list) or not payload:
        raise BoundaryDataError(f"OpenStreetMap returned no result for {osm_id}.")
    result = payload[0]
    if str(result.get("osm_id")) != osm_id[1:]:
        raise BoundaryDataError(
            f"OpenStreetMap returned a different feature for requested {osm_id}."
        )
    if not result.get("lat") or not result.get("lon"):
        raise BoundaryDataError(f"OpenStreetMap result {osm_id} has no coordinates.")
    return result
