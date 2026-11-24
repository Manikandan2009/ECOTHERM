import json
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import pyogrio
import requests
from shapely.geometry import LineString, Point, Polygon, box

from app.services.study_areas import StudyArea


class OpenStreetMapError(RuntimeError):
    """Raised when OSM features cannot be fetched or parsed."""


OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
OVERPASS_USER_AGENT = "ECOTHERM urban heat research demo (local application)"
OSM_CATEGORIES = {
    "hospital": {
        "amenity": {"hospital", "clinic", "doctors"},
        "healthcare": {"hospital", "clinic"},
    },
    "park": {"leisure": {"park", "garden", "playground"}},
    "water": {
        "natural": {"water"},
        "waterway": {"river", "stream", "canal"},
        "amenity": {"drinking_water"},
        "drinking_water": {"yes"},
    },
    "bus_stop": {
        "highway": {"bus_stop"},
        "public_transport": {"platform", "stop_position"},
    },
    "market": {"amenity": {"marketplace"}},
}
GEOFABRIK_EXTRACT_NAME = "southern-zone-latest.osm.pbf"
GEOFABRIK_EXTRACT_URL = (
    "https://download.geofabrik.de/asia/india/southern-zone/"
    "southern-zone-latest.osm.pbf"
)
OSM_EXTRACT_CONFIG = """\
[general]
closed_ways_are_polygons=amenity,building,leisure,natural,public_transport=platform,highway=platform
tags_format=json

[points]
osm_id=yes
attributes=name,amenity,healthcare,highway,public_transport,drinking_water,natural,waterway
other_tags=no

[lines]
osm_id=yes
attributes=name,highway,waterway
other_tags=no

[multipolygons]
osm_id=yes
attributes=name,amenity,healthcare,building,leisure,natural,waterway,public_transport,drinking_water
other_tags=no
"""
OSM_EXTRACT_LAYERS = {
    "points": {
        "columns": [
            "osm_id",
            "amenity",
            "healthcare",
            "highway",
            "public_transport",
            "drinking_water",
            "natural",
            "waterway",
        ],
        "where": (
            "amenity IN ('hospital','clinic','doctors','marketplace','drinking_water') "
            "OR healthcare IN ('hospital','clinic') OR highway = 'bus_stop' "
            "OR public_transport IN ('platform','stop_position') "
            "OR drinking_water = 'yes' OR natural = 'water' "
            "OR waterway IN ('river','stream','canal')"
        ),
    },
    "lines": {
        "columns": ["osm_id", "highway", "waterway"],
        "where": (
            "highway IS NOT NULL "
            "OR waterway IN ('river','stream','canal')"
        ),
    },
    "multipolygons": {
        "columns": [
            "osm_id",
            "osm_way_id",
            "amenity",
            "healthcare",
            "building",
            "leisure",
            "natural",
            "waterway",
            "public_transport",
            "drinking_water",
        ],
        "where": (
            "(building IS NOT NULL AND building NOT IN ('no','ruins')) "
            "OR amenity IN ('hospital','clinic','doctors','marketplace','drinking_water') "
            "OR healthcare IN ('hospital','clinic') "
            "OR leisure IN ('park','garden','playground') "
            "OR natural = 'water' "
            "OR waterway IN ('river','stream','canal') "
            "OR public_transport IN ('platform','stop_position')"
        ),
    },
}


def fetch_city_features(
    area: StudyArea,
    cache_dir: Path,
    *,
    force_refresh: bool = False,
) -> tuple[gpd.GeoDataFrame, dict[str, Any]]:
    cache_path = cache_dir / "raw" / "openstreetmap" / f"{area.region_id}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.is_file() and not force_refresh:
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OpenStreetMapError(
                f"Cached OSM response {cache_path.name} is invalid; "
                "reacquire it explicitly."
            ) from exc
        from_cache = True
    else:
        query = _overpass_query(area)
        payload = _request_overpass(query)
        temporary_path = cache_path.with_suffix(".tmp")
        try:
            temporary_path.write_text(
                json.dumps(payload, separators=(",", ":")),
                encoding="utf-8",
            )
            temporary_path.replace(cache_path)
        except OSError as exc:
            raise OpenStreetMapError(
                f"Could not cache the OSM response: {exc}"
            ) from exc
        from_cache = False

    features = _to_feature_frame(payload)
    manifest = {
        "provider": "OpenStreetMap via Overpass API",
        "license": "Open Database License 1.0 (ODbL)",
        "attribution": "© OpenStreetMap contributors",
        "copyright_url": "https://www.openstreetmap.org/copyright",
        "region_id": area.region_id,
        "query_bbox": _area_bounds(area),
        "feature_count": len(features),
        "feature_categories": (
            features.category.value_counts().to_dict()
            if not features.empty
            else {}
        ),
        "data_status": "derived_osm_mapped_features",
        "source_completeness": (
            "OpenStreetMap feature completeness is not guaranteed; counts describe "
            "mapped objects only."
        ),
        "from_cache": from_cache,
        "cache_file": str(cache_path),
    }
    return features, manifest


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def process_geofabrik_extract(
    cache_dir: Path,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    extract_path = cache_dir / "raw" / "openstreetmap" / GEOFABRIK_EXTRACT_NAME
    boundary_path = cache_dir / "processed" / "boundaries" / "regions.geojson"
    output_path = (
        cache_dir / "processed" / "openstreetmap" / "tamil_nadu_summary.json"
    )
    if not extract_path.is_file():
        raise OpenStreetMapError(
            f"Geofabrik extract is missing: {extract_path}"
        )
    if not boundary_path.is_file():
        raise OpenStreetMapError(
            f"Cached Tamil Nadu boundary is missing: {boundary_path}"
        )

    extract_sha256 = _sha256_file(extract_path)
    try:
        boundaries = gpd.read_file(boundary_path)
        state_rows = boundaries.loc[boundaries["region_id"] == "tamil_nadu"]
        if state_rows.empty or state_rows.geometry.iloc[0] is None:
            raise OpenStreetMapError(
                "The cached regions boundary does not contain Tamil Nadu."
            )
        state_geometry = state_rows.geometry.iloc[0]
        if state_geometry.is_empty or not state_geometry.is_valid:
            raise OpenStreetMapError(
                "The cached Tamil Nadu boundary is empty or invalid."
            )
    except (OSError, ValueError, KeyError) as exc:
        raise OpenStreetMapError(
            f"Could not read the cached Tamil Nadu boundary: {exc}"
        ) from exc

    boundary_sha256 = hashlib.sha256(state_geometry.wkb).hexdigest()
    if output_path.is_file() and not force_refresh:
        try:
            cached = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OpenStreetMapError(
                f"Cached OSM summary {output_path.name} is invalid; "
                "reprocess the extract explicitly."
            ) from exc
        if (
            cached.get("source_extract", {}).get("sha256") == extract_sha256
            and cached.get("state_boundary_sha256") == boundary_sha256
        ):
            return cached

    projected_boundary = (
        gpd.GeoSeries([state_geometry], crs=boundaries.crs or "EPSG:4326")
        .to_crs("EPSG:32644")
        .iloc[0]
    )
    buffered_boundary = projected_boundary.buffer(5000)
    bbox = tuple(
        float(value)
        for value in gpd.GeoSeries(
            [buffered_boundary],
            crs="EPSG:32644",
        ).to_crs("EPSG:4326").total_bounds
    )
    category_ids: dict[str, set[str]] = {
        "buildings": set(),
        "roads": set(),
        "hospitals": set(),
        "parks": set(),
        "water_features": set(),
        "bus_stops": set(),
        "markets": set(),
    }
    all_feature_ids: set[str] = set()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_directory = cache_dir / "tmp"
    temporary_directory.mkdir(parents=True, exist_ok=True)
    config_path = temporary_directory / "osmconf.ini"
    config_path.write_text(OSM_EXTRACT_CONFIG, encoding="utf-8")
    config_keys = (
        "OSM_CONFIG_FILE",
        "CPL_TMPDIR",
        "OSM_COMPRESS_NODES",
        "OSM_MAX_TMPFILE_SIZE",
    )
    previous_config = {
        key: pyogrio.get_gdal_config_option(key) for key in config_keys
    }
    pyogrio.set_gdal_config_options(
        {
            "OSM_CONFIG_FILE": str(config_path),
            "CPL_TMPDIR": str(temporary_directory),
            "OSM_COMPRESS_NODES": "YES",
            "OSM_MAX_TMPFILE_SIZE": "500",
        }
    )
    try:
        for layer_name, layer_config in OSM_EXTRACT_LAYERS.items():
            try:
                features = pyogrio.read_dataframe(
                    extract_path,
                    layer=layer_name,
                    columns=layer_config["columns"],
                    where=layer_config["where"],
                    bbox=bbox,
                )
            except (OSError, ValueError, RuntimeError) as exc:
                raise OpenStreetMapError(
                    f"Could not read the {layer_name} layer from the "
                    f"Geofabrik extract: {exc}"
                ) from exc
            if features.empty:
                continue
            try:
                inside_state = (
                    features.geometry.notna()
                    & ~features.geometry.is_empty
                    & features.geometry.intersects(state_geometry)
                )
            except (ValueError, RuntimeError) as exc:
                raise OpenStreetMapError(
                    f"Could not spatially filter the {layer_name} OSM features: {exc}"
                ) from exc
            features = features.loc[inside_state]
            if features.empty:
                continue
            object_ids = _extract_object_ids(features, layer_name)
            all_feature_ids.update(object_ids.tolist())

            tags = {
                column: (
                    features[column].fillna("").astype(str).str.casefold()
                    if column in features
                    else pd.Series("", index=features.index, dtype="string")
                )
                for column in (
                    "amenity",
                    "healthcare",
                    "building",
                    "highway",
                    "leisure",
                    "natural",
                    "waterway",
                    "public_transport",
                    "drinking_water",
                )
            }
            category_masks = {
                "buildings": (
                    tags["building"].ne("")
                    & ~tags["building"].isin({"no", "ruins"})
                ).to_numpy(),
                "roads": (
                    tags["highway"].ne("")
                    if layer_name == "lines"
                    else pd.Series(False, index=features.index)
                ).to_numpy(),
                "hospitals": (
                    tags["amenity"].isin({"hospital", "clinic", "doctors"})
                    | tags["healthcare"].isin({"hospital", "clinic"})
                ).to_numpy(),
                "parks": tags["leisure"].isin({"park", "garden", "playground"}).to_numpy(),
                "water_features": (
                    tags["natural"].eq("water")
                    | tags["waterway"].isin({"river", "stream", "canal"})
                    | tags["amenity"].eq("drinking_water")
                    | tags["drinking_water"].eq("yes")
                ).to_numpy(),
                "bus_stops": (
                    tags["highway"].eq("bus_stop")
                    | tags["public_transport"].isin({"platform", "stop_position"})
                ).to_numpy(),
                "markets": tags["amenity"].eq("marketplace").to_numpy(),
            }
            for category, mask in category_masks.items():
                category_ids[category].update(object_ids.loc[mask].tolist())
    finally:
        pyogrio.set_gdal_config_options(previous_config)

    extract_stat = extract_path.stat()
    result = {
        "provider": "Geofabrik Southern Zone OpenStreetMap extract",
        "source_url": GEOFABRIK_EXTRACT_URL,
        "license": "Open Database License 1.0 (ODbL)",
        "attribution": "© OpenStreetMap contributors",
        "copyright_url": "https://www.openstreetmap.org/copyright",
        "region_id": "tamil_nadu",
        "data_status": "derived_osm_mapped_features",
        "feature_counts": {
            category: len(feature_ids)
            for category, feature_ids in category_ids.items()
        },
        "total_feature_count": len(all_feature_ids),
        "count_method": (
            "Unique tagged OSM nodes, ways, and relations from the cached extract; "
            "point, line, and polygon features are counted when their geometry "
            "intersects the cached Tamil Nadu boundary."
        ),
        "source_completeness": (
            "Counts describe mapped OSM objects in this extract only. "
            "OpenStreetMap coverage is not complete or uniform."
        ),
        "state_boundary_sha256": boundary_sha256,
        "source_extract": {
            "file": GEOFABRIK_EXTRACT_NAME,
            "sha256": extract_sha256,
            "size_bytes": extract_stat.st_size,
            "last_modified_utc": datetime.fromtimestamp(
                extract_stat.st_mtime,
                tz=timezone.utc,
            ).isoformat(),
        },
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "processing": {
            "library": "GDAL OSM driver via Pyogrio",
            "gdal_version": ".".join(str(part) for part in pyogrio.__gdal_version__),
            "boundary_buffer_m": 5000,
            "feature_bbox_wgs84": list(bbox),
            "geometry_warning_note": (
                "GDAL reported some unclosed or invalid polygon rings in the "
                "extract; affected geometries may be omitted from these counts."
            ),
        },
    }
    temporary_path = output_path.with_suffix(".tmp")
    try:
        temporary_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(output_path)
    except OSError as exc:
        raise OpenStreetMapError(
            f"Could not write the processed OSM summary: {exc}"
        ) from exc
    return result


def _extract_object_ids(features: gpd.GeoDataFrame, layer_name: str) -> pd.Series:
    if layer_name == "multipolygons":
        way_ids = features["osm_way_id"]
        relation_ids = features["osm_id"]
        return pd.Series(
            [
                f"way:{int(way_id)}" if pd.notna(way_id) else f"relation:{int(relation_id)}"
                for way_id, relation_id in zip(
                    way_ids,
                    relation_ids,
                    strict=True,
                )
            ],
            index=features.index,
            dtype="string",
        )
    osm_type = "node" if layer_name == "points" else "way"
    return features["osm_id"].map(lambda value: f"{osm_type}:{int(value)}")


def enrich_city_grid_records(
    records: pd.DataFrame,
    features: gpd.GeoDataFrame,
) -> pd.DataFrame:
    output = records.copy()
    metric_columns = (
        "osm_building_count",
        "osm_building_density_per_km2",
        "distance_to_hospital_m",
        "distance_to_park_m",
        "distance_to_water_m",
        "distance_to_bus_stop_m",
        "distance_to_market_m",
        "distance_to_road_m",
    )
    for column in metric_columns:
        output[column] = pd.NA
    output["osm_wide_road_mapped_nearby"] = pd.NA
    output["osm_data_status"] = "unavailable"
    if features.empty:
        return output

    cell_points = gpd.GeoDataFrame(
        output[["grid_id", "centroid_lon", "centroid_lat", "resolution_m"]],
        geometry=gpd.points_from_xy(output.centroid_lon, output.centroid_lat),
        crs="EPSG:4326",
    ).to_crs("EPSG:32644")
    half_size = cell_points.resolution_m.astype(float) / 2
    cell_polygons = cell_points.copy()
    cell_polygons["geometry"] = [
        box(point.x - radius, point.y - radius, point.x + radius, point.y + radius)
        for point, radius in zip(cell_points.geometry, half_size, strict=True)
    ]
    features = features.to_crs("EPSG:32644")

    buildings = features[features.category == "building"]
    if not buildings.empty:
        building_points = gpd.GeoDataFrame(
            geometry=buildings.geometry.centroid,
            crs="EPSG:32644",
        )
        counts = gpd.sjoin(
            building_points,
            cell_polygons[["grid_id", "geometry"]],
            how="inner",
            predicate="within",
        ).groupby("grid_id").size()
        output["osm_building_count"] = (
            output.grid_id.map(counts).fillna(0).astype("Int64")
        )
        cell_area_km2 = (output.resolution_m.astype(float) / 1000) ** 2
        output["osm_building_density_per_km2"] = (
            output["osm_building_count"].astype(float) / cell_area_km2
        )
    else:
        output["osm_building_count"] = 0
        output["osm_building_density_per_km2"] = 0.0

    center_points = cell_points.copy()
    distance_columns = {
        "hospital": "distance_to_hospital_m",
        "park": "distance_to_park_m",
        "water": "distance_to_water_m",
        "bus_stop": "distance_to_bus_stop_m",
        "market": "distance_to_market_m",
        "road": "distance_to_road_m",
    }
    for category, column in distance_columns.items():
        category_features = features[features.category == category]
        if category_features.empty:
            continue
        nearest = gpd.sjoin_nearest(
            center_points[["grid_id", "geometry"]],
            category_features[["geometry"]],
            how="left",
            distance_col=column,
        ).drop_duplicates("grid_id")
        distances = nearest.set_index("grid_id")[column]
        output[column] = output.grid_id.map(distances)

    roads = features[features.category == "road"]
    if not roads.empty:
        nearest_roads = gpd.sjoin_nearest(
            center_points[["grid_id", "geometry"]],
            roads[["highway", "geometry"]],
            how="left",
            distance_col="distance_to_road_m",
        ).drop_duplicates("grid_id")
        output["distance_to_road_m"] = output.grid_id.map(
            nearest_roads.set_index("grid_id")["distance_to_road_m"]
        )
        nearest_by_id = nearest_roads.drop_duplicates("grid_id").set_index("grid_id")
        major_road = nearest_by_id["highway"].isin(
            {"trunk", "primary", "secondary"}
        )
        close_road = nearest_by_id["distance_to_road_m"] <= output.set_index(
            "grid_id"
        )["resolution_m"]
        output["osm_wide_road_mapped_nearby"] = output.grid_id.map(
            major_road & close_road
        )
    output["osm_data_status"] = "osm_mapped_proxy"
    return output


def _overpass_query(area: StudyArea) -> str:
    south, west, north, east = _area_bounds(area)
    bbox = f"{south},{west},{north},{east}"
    return (
        "[out:json][timeout:90];("
        f'way["building"]({bbox});'
        f'way["highway"]({bbox});'
        f'node["amenity"~"hospital|clinic|doctors|marketplace|drinking_water"]({bbox});'
        f'way["amenity"~"hospital|clinic|doctors|marketplace|drinking_water"]({bbox});'
        f'node["healthcare"~"hospital|clinic"]({bbox});'
        f'way["healthcare"~"hospital|clinic"]({bbox});'
        f'way["leisure"~"park|garden|playground"]({bbox});'
        f'way["natural"="water"]({bbox});'
        f'way["waterway"~"river|stream|canal"]({bbox});'
        f'node["highway"="bus_stop"]({bbox});'
        f'node["public_transport"~"platform|stop_position"]({bbox});'
        ");out geom;"
    )


def _area_bounds(area: StudyArea) -> tuple[float, float, float, float]:
    projected = (
        gpd.GeoSeries([area.geometry], crs="EPSG:4326")
        .to_crs("EPSG:32644")
        .iloc[0]
        .buffer(5000)
    )
    geographic = gpd.GeoSeries([projected], crs="EPSG:32644").to_crs("EPSG:4326")
    min_x, min_y, max_x, max_y = geographic.total_bounds
    return float(min_y), float(min_x), float(max_y), float(max_x)


def _request_overpass(query: str) -> dict[str, Any]:
    failures: list[str] = []
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            response = requests.post(
                endpoint,
                data={"data": query},
                headers={
                    "User-Agent": OVERPASS_USER_AGENT,
                    "Accept": "application/json",
                },
                timeout=(20, 120),
            )
            if response.status_code in (429, 502, 503, 504):
                failures.append(f"{endpoint}: HTTP {response.status_code}")
                time.sleep(1)
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(
                payload.get("elements"), list
            ):
                raise OpenStreetMapError(
                    f"{endpoint} returned an invalid Overpass response."
                )
            return payload
        except (requests.RequestException, ValueError) as exc:
            failures.append(f"{endpoint}: {exc}")
    detail = "; ".join(failures)
    raise OpenStreetMapError(
        f"OpenStreetMap Overpass queries failed for this city extent: {detail}"
    )


def _to_feature_frame(payload: dict[str, Any]) -> gpd.GeoDataFrame:
    rows: list[dict[str, Any]] = []
    for element in payload["elements"]:
        tags = element.get("tags", {})
        category = _classify(tags)
        if category is None:
            continue
        geometry = _element_geometry(element, category)
        if geometry is None or geometry.is_empty:
            continue
        rows.append(
            {
                "osm_type": element.get("type"),
                "osm_id": element.get("id"),
                "category": category,
                "highway": tags.get("highway"),
                "building": tags.get("building"),
                "tags_json": json.dumps(tags, sort_keys=True),
                "geometry": geometry,
            }
        )
    if not rows:
        return gpd.GeoDataFrame(
            columns=(
                "osm_type",
                "osm_id",
                "category",
                "highway",
                "building",
                "tags_json",
                "geometry",
            ),
            geometry="geometry",
            crs="EPSG:4326",
        )
    features = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    return features.drop_duplicates(["osm_type", "osm_id"])


def _classify(tags: dict[str, str]) -> str | None:
    if tags.get("building") and tags["building"] not in ("no", "ruins"):
        return "building"
    if tags.get("highway"):
        return "road"
    for category, rules in OSM_CATEGORIES.items():
        if any(tags.get(key) in values for key, values in rules.items()):
            return category
    return None


def _element_geometry(element: dict[str, Any], category: str) -> Any:
    if element.get("type") == "node":
        if element.get("lat") is None or element.get("lon") is None:
            return None
        return Point(float(element["lon"]), float(element["lat"]))
    coordinates = [
        (float(point["lon"]), float(point["lat"]))
        for point in element.get("geometry", [])
        if "lon" in point and "lat" in point
    ]
    if len(coordinates) < 2:
        center = element.get("center")
        if center and "lon" in center and "lat" in center:
            return Point(float(center["lon"]), float(center["lat"]))
        return None
    if category in ("building", "park", "water") and coordinates[0] == coordinates[-1]:
        polygon = Polygon(coordinates)
        return polygon if polygon.is_valid else polygon.buffer(0)
    return LineString(coordinates)
