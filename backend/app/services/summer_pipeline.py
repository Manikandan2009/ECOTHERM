import asyncio
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import geopandas as gpd
import ee
import rasterio
from rasterio.merge import merge
from shapely.geometry import box

from app.core.settings import Settings
from app.repositories.sqlite_store import (
    GridPersistenceError,
    save_district_summaries,
    save_grid_observations,
    save_weather_observations,
)
from app.services.district_aggregates import (
    aggregate_grid_to_districts,
    write_district_outputs,
)
from app.services.earth_engine import EarthEngineClient, EarthEngineDataError
from app.services.grid_processing import (
    GridProcessingError,
    WORLDPOP_AGGREGATION_VERSION,
    raster_to_grid_records,
    write_grid_csv,
)
from app.services.open_meteo import (
    OpenMeteoClient,
    OpenMeteoError,
)
from app.services.open_street_map import (
    OpenStreetMapError,
    enrich_city_grid_records,
    fetch_city_features,
)
from app.services.satellite_export import export_summer_grid_geotiff
from app.services.study_areas import (
    BoundaryDataError,
    StudyArea,
    load_districts,
    load_study_areas,
)


def run_summer_pipeline(
    settings: Settings,
    *,
    year: int,
    region_ids: list[str] | None = None,
    force_refresh: bool = False,
    skip_weather: bool = False,
    skip_osm: bool = False,
) -> dict[str, Any]:
    areas, boundary_manifest = load_study_areas(
        settings.cache_dir,
        refresh_boundaries=force_refresh,
    )
    districts, district_manifest = load_districts(
        settings.cache_dir,
        areas["tamil_nadu"],
        refresh=force_refresh,
    )
    selected_ids = region_ids or list(areas)
    unknown_ids = set(selected_ids) - set(areas)
    if unknown_ids:
        raise ValueError(f"Unknown region IDs: {', '.join(sorted(unknown_ids))}")

    earth_engine = EarthEngineClient(settings.earth_engine_project_id)
    earth_engine.initialize()
    database_path = settings.cache_dir / "processed" / "ecotherm.sqlite"
    output_directory = settings.cache_dir / "processed"
    grid_directory = output_directory / "grids"
    raster_directory = settings.cache_dir / "raw" / "earth_engine"
    manifest_directory = output_directory / "manifests"
    result: dict[str, Any] = {
        "year": year,
        "database": str(database_path),
        "regions": {},
        "districts": {
            "boundary_count": len(districts),
            "source": district_manifest,
            "summary": None,
        },
        "weather": {},
        "osm": {},
        "errors": [],
    }

    for region_id in selected_ids:
        area = areas[region_id]
        raster_path = raster_directory / (
            f"{region_id}_{year}_{area.resolution_m}m.tif"
        )
        export_manifest_path = raster_path.with_suffix(".json")
        try:
            if region_id == "tamil_nadu":
                export_metadata = _export_statewide_tiled(
                    earth_engine,
                    area,
                    year=year,
                    raster_path=raster_path,
                    force_refresh=force_refresh,
                    tile_size_m=50_000,
                )
            elif force_refresh or not (
                raster_path.is_file() and export_manifest_path.is_file()
            ):
                geometry = ee.Geometry(area.geometry.__geo_interface__)
                scene_counts, acquisition = export_summer_grid_geotiff(
                    earth_engine,
                    geometry,
                    region_id=region_id,
                    year=year,
                    resolution_m=area.resolution_m,
                    output_path=raster_path,
                )
                export_metadata = {
                    "scene_counts": scene_counts,
                    "acquisition": acquisition,
                }
                export_manifest_path.write_text(
                    json.dumps(export_metadata, indent=2),
                    encoding="utf-8",
                )
            else:
                try:
                    export_metadata = json.loads(
                        export_manifest_path.read_text(encoding="utf-8")
                    )
                except (OSError, ValueError) as exc:
                    raise GridProcessingError(
                        f"Cached raster manifest {export_manifest_path.name} is invalid."
                    ) from exc

            records, manifest = raster_to_grid_records(
                raster_path,
                area,
                season_year=year,
                scene_counts=export_metadata["scene_counts"],
                acquisition=export_metadata["acquisition"],
                boundary_manifest=boundary_manifest,
            )
            osm_status: dict[str, Any] = {"status": "not_applicable"}
            if region_id != "tamil_nadu":
                if skip_osm:
                    osm_status = {
                        "status": "not_attempted",
                        "reason": "OSM acquisition skipped by command option.",
                    }
                else:
                    try:
                        features, osm_manifest = fetch_city_features(
                            area,
                            settings.cache_dir,
                            force_refresh=force_refresh,
                        )
                        records = enrich_city_grid_records(records, features)
                        osm_status = {"status": "available", **osm_manifest}
                        processed_osm_dir = output_directory / "openstreetmap"
                        processed_osm_dir.mkdir(parents=True, exist_ok=True)
                        features.to_file(
                            processed_osm_dir / f"{region_id}_features.geojson",
                            driver="GeoJSON",
                        )
                    except OpenStreetMapError as exc:
                        osm_status = {
                            "status": "unavailable",
                            "error": str(exc),
                            "data_status": "missing",
                        }
                        result["errors"].append(
                            {"region_id": region_id, "source": "OpenStreetMap", "error": str(exc)}
                        )
            manifest["openstreetmap"] = osm_status
            csv_path = grid_directory / f"{region_id}_{area.resolution_m}m_{year}.csv"
            write_grid_csv(records, csv_path)
            saved_count = save_grid_observations(database_path, records, manifest)
            manifest_directory.mkdir(parents=True, exist_ok=True)
            (manifest_directory / f"{region_id}_{year}.json").write_text(
                json.dumps(manifest, indent=2, default=str),
                encoding="utf-8",
            )
            result["regions"][region_id] = {
                "status": "available",
                "cell_count": saved_count,
                "csv": str(csv_path),
                "raster": str(raster_path),
                "manifest_id": manifest["manifest_id"],
                "coverage": manifest["coverage"],
                "scene_counts": manifest["scene_counts"],
            }
            result["osm"][region_id] = osm_status
        except (EarthEngineDataError, GridProcessingError, GridPersistenceError) as exc:
            result["regions"][region_id] = {"status": "unavailable", "error": str(exc)}
            result["errors"].append(
                {"region_id": region_id, "source": "Earth Engine/grid pipeline", "error": str(exc)}
            )

        if not skip_weather:
            try:
                latitude, longitude = _weather_reference(area)
                weather = asyncio.run(
                    OpenMeteoClient(
                        archive_url=settings.open_meteo_archive_url,
                        cache_dir=settings.cache_dir,
                        timeout_seconds=settings.open_meteo_timeout_seconds,
                    ).fetch_daily(
                        location_id=f"{region_id}_reference",
                        latitude=latitude,
                        longitude=longitude,
                        start_date=date(year, 4, 1),
                        end_date=date(year, 6, 30),
                        force_refresh=force_refresh,
                    )
                )
                daily_count, hourly_count = save_weather_observations(
                    database_path,
                    weather.data,
                )
                result["weather"][region_id] = {
                    "status": "available",
                    "location_id": weather.data.location_id,
                    "daily_rows": daily_count,
                    "hourly_rows": hourly_count,
                    "model": weather.data.provenance.model,
                    "spatial_support": weather.data.provenance.spatial_support,
                    "data_status": weather.data.provenance.data_status,
                    "from_cache": weather.from_cache,
                }
            except OpenMeteoError as exc:
                result["weather"][region_id] = {
                    "status": "unavailable",
                    "error": str(exc),
                }
                result["errors"].append(
                    {"region_id": region_id, "source": "Open-Meteo", "error": str(exc)}
                )
        else:
            result["weather"][region_id] = {
                "status": "not_attempted",
                "reason": "weather acquisition skipped by command option",
            }

    state_summary = result["regions"].get("tamil_nadu")
    if (
        "tamil_nadu" in selected_ids
        and state_summary
        and state_summary["status"] == "available"
    ):
        try:
            import pandas as pd

            state_records = pd.read_csv(state_summary["csv"])
            district_summary = aggregate_grid_to_districts(
                state_records,
                districts,
                season_year=year,
            )
            csv_path, geojson_path = write_district_outputs(
                district_summary,
                districts,
                output_directory / "districts",
            )
            saved_count = save_district_summaries(
                database_path,
                district_summary,
                boundary_manifest=district_manifest,
            )
            result["districts"]["summary"] = {
                "status": "available",
                "districts_with_data": saved_count,
                "csv": str(csv_path),
                "geojson": str(geojson_path),
                "aggregation": (
                    "1 km cell-center assignment; boundary-edge allocation uncertainty "
                    "is not area-weighted"
                ),
            }
        except (GridProcessingError, GridPersistenceError, OSError, ValueError) as exc:
            result["districts"]["summary"] = {
                "status": "unavailable",
                "error": str(exc),
            }
            result["errors"].append(
                {"source": "district aggregation", "error": str(exc)}
            )

    (output_directory / "summer_pipeline_manifest.json").write_text(
        json.dumps(result, indent=2, default=str),
        encoding="utf-8",
    )
    return result


def _weather_reference(area: StudyArea) -> tuple[float, float]:
    if area.region_id == "tamil_nadu":
        centroid = (
            gpd.GeoSeries([area.geometry], crs="EPSG:4326")
            .to_crs("EPSG:32644")
            .centroid.to_crs("EPSG:4326")
            .iloc[0]
        )
        return float(centroid.y), float(centroid.x)
    return (
        float(area.metadata["center_latitude"]),
        float(area.metadata["center_longitude"]),
    )


def _export_statewide_tiled(
    client: EarthEngineClient,
    area: StudyArea,
    *,
    year: int,
    raster_path: Path,
    force_refresh: bool,
    tile_size_m: int,
) -> dict[str, Any]:
    raster_path.parent.mkdir(parents=True, exist_ok=True)
    export_manifest_path = raster_path.with_suffix(".json")
    projected_boundary = (
        gpd.GeoSeries([area.geometry], crs="EPSG:4326")
        .to_crs("EPSG:32644")
        .iloc[0]
    )
    min_x, min_y, max_x, max_y = projected_boundary.bounds
    min_tile_x = math.floor(min_x / tile_size_m)
    max_tile_x = math.ceil(max_x / tile_size_m)
    min_tile_y = math.floor(min_y / tile_size_m)
    max_tile_y = math.ceil(max_y / tile_size_m)
    tile_directory = raster_path.parent / f"{area.region_id}_{year}_tiles"
    tile_directory.mkdir(parents=True, exist_ok=True)
    tile_paths: list[Path] = []
    tile_records: list[dict[str, Any]] = []
    for tile_x in range(min_tile_x, max_tile_x):
        for tile_y in range(min_tile_y, max_tile_y):
            left = tile_x * tile_size_m
            bottom = tile_y * tile_size_m
            right = left + tile_size_m
            top = bottom + tile_size_m
            if not projected_boundary.intersects(box(left, bottom, right, top)):
                continue
            tile_id = f"x{tile_x}_y{tile_y}"
            tile_path = tile_directory / f"{tile_id}.tif"
            tile_manifest_path = tile_path.with_suffix(".json")
            if force_refresh or not (
                tile_path.is_file() and tile_manifest_path.is_file()
            ):
                tile_geometry = ee.Geometry.Rectangle(
                    [left, bottom, right, top],
                    proj="EPSG:32644",
                    geodesic=False,
                )
                scene_counts, acquisition = export_summer_grid_geotiff(
                    client,
                    tile_geometry,
                    region_id=f"{area.region_id}_{tile_id}",
                    year=year,
                    resolution_m=area.resolution_m,
                    output_path=tile_path,
                )
                tile_manifest = {
                    "tile_id": tile_id,
                    "tile_bounds_epsg32644": [left, bottom, right, top],
                    "scene_counts": scene_counts,
                    "acquisition": acquisition,
                }
                tile_manifest_path.write_text(
                    json.dumps(tile_manifest, indent=2),
                    encoding="utf-8",
                )
            else:
                try:
                    tile_manifest = json.loads(
                        tile_manifest_path.read_text(encoding="utf-8")
                    )
                except (OSError, ValueError) as exc:
                    raise GridProcessingError(
                        f"Cached state tile manifest {tile_manifest_path.name} is invalid."
                    ) from exc
            tile_paths.append(tile_path)
            tile_records.append(tile_manifest)
    if not tile_paths:
        raise GridProcessingError("No statewide raster tiles intersect Tamil Nadu.")

    try:
        sources = [rasterio.open(path) for path in tile_paths]
        try:
            mosaic, transform = merge(
                sources,
                nodata=-9999,
                dtype="float64",
                method="first",
            )
            profile = sources[0].profile.copy()
            profile.update(
                driver="GTiff",
                height=mosaic.shape[1],
                width=mosaic.shape[2],
                transform=transform,
                count=mosaic.shape[0],
                nodata=-9999,
                compress="deflate",
            )
            temporary_path = raster_path.with_name(
                f".{raster_path.stem}.mosaic.tmp.tif"
            )
            try:
                with rasterio.open(temporary_path, "w", **profile) as output:
                    output.write(mosaic)
                    for band_index, description in enumerate(
                        sources[0].descriptions,
                        start=1,
                    ):
                        output.set_band_description(band_index, description)
                    aggregation_versions = {
                        source.tags().get("worldpop_aggregation_version")
                        for source in sources
                    }
                    if aggregation_versions == {WORLDPOP_AGGREGATION_VERSION}:
                        output.update_tags(
                            worldpop_aggregation_version=WORLDPOP_AGGREGATION_VERSION
                        )
                temporary_path.replace(raster_path)
            except OSError as exc:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    raise GridProcessingError(
                        f"State mosaic write failed and temporary file cleanup "
                        f"failed: {cleanup_error}"
                    ) from exc
                raise GridProcessingError(
                    f"Could not write statewide tile mosaic: {exc}"
                ) from exc
        finally:
            for source in sources:
                source.close()
    except rasterio.errors.RasterioError as exc:
        raise GridProcessingError(
            f"Could not assemble statewide Earth Engine tiles: {exc}"
        ) from exc

    group_counts = {
        key: max(
            int(record["scene_counts"].get(key, 0))
            for record in tile_records
        )
        for key in tile_records[0]["scene_counts"]
    }
    export_metadata = {
        "scene_counts": group_counts,
        "acquisition": {
            "start_date": f"{year}-04-01",
            "end_date": f"{year}-06-30",
            "crs": "EPSG:32644",
            "nodata": "-9999",
            "tile_size_m": tile_size_m,
            "tile_count": len(tile_paths),
            "tile_scene_counts_note": (
                "Scene counts are the maximum count in any tile, not a sum of "
                "unique statewide scenes."
            ),
            "download_bytes": str(raster_path.stat().st_size),
        },
        "tiles": tile_records,
    }
    export_manifest_path.write_text(
        json.dumps(export_metadata, indent=2),
        encoding="utf-8",
    )
    return export_metadata
