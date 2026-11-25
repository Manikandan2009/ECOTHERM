import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Geod
from rasterio.warp import transform as transform_coordinates
from shapely.geometry import Point, box

from app.services.study_areas import StudyArea


RASTER_BANDS = (
    "lst_c",
    "lst_valid_scenes",
    "ndvi",
    "ndvi_valid_scenes",
    "ndbi",
    "ndbi_valid_scenes",
    "ndwi",
    "ndwi_valid_scenes",
    "population_estimated_2025",
    "population_age_2020",
    "children_estimated_2020",
    "elderly_estimated_2020",
)
WORLDPOP_AGGREGATION_VERSION = "area_weighted_count_sum_v1"
WORLDPOP_PIXEL_SIZE_DEGREES = 3 / 3600
POPULATION_BANDS = (
    "population_estimated_2025",
    "population_age_2020",
    "children_estimated_2020",
    "elderly_estimated_2020",
)


class GridProcessingError(RuntimeError):
    """Raised when an Earth Engine grid raster cannot be safely processed."""


def raster_to_grid_records(
    raster_path: Path,
    area: StudyArea,
    *,
    season_year: int,
    scene_counts: dict[str, int],
    acquisition: dict[str, str],
    boundary_manifest: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        with rasterio.open(raster_path) as dataset:
            if dataset.count != len(RASTER_BANDS):
                raise GridProcessingError(
                    f"{raster_path.name} has {dataset.count} bands; "
                    f"expected {len(RASTER_BANDS)}."
                )
            if dataset.crs is None or dataset.transform.a <= 0 or dataset.transform.e >= 0:
                raise GridProcessingError(
                    f"{raster_path.name} does not have a north-up projected grid."
                )
            raster_values = dataset.read(out_dtype="float64")
            transform = dataset.transform
            width, height = dataset.width, dataset.height
            raster_crs = dataset.crs
            nodata = dataset.nodata if dataset.nodata is not None else -9999
            population_aggregation_version = dataset.tags().get(
                "worldpop_aggregation_version"
            )
    except (OSError, rasterio.errors.RasterioError) as exc:
        raise GridProcessingError(f"Could not read raster {raster_path.name}: {exc}") from exc

    population_legacy_corrected = (
        area.resolution_m == 1000
        and population_aggregation_version != WORLDPOP_AGGREGATION_VERSION
    )
    if population_legacy_corrected:
        row_factors = _legacy_worldpop_area_factors(
            transform,
            height=height,
            raster_crs=raster_crs,
            target_resolution_m=area.resolution_m,
        )
        row_factor_grid = np.broadcast_to(
            row_factors[:, np.newaxis],
            (height, width),
        )
        for band in POPULATION_BANDS:
            band_index = RASTER_BANDS.index(band)
            band_values = raster_values[band_index]
            valid = np.isfinite(band_values) & (band_values != nodata)
            band_values[valid] *= row_factor_grid[valid]

    rows, columns = np.indices((height, width))
    center_x = (
        transform.c
        + (columns + 0.5) * transform.a
        + (rows + 0.5) * transform.b
    )
    center_y = (
        transform.f
        + (columns + 0.5) * transform.d
        + (rows + 0.5) * transform.e
    )
    values = {
        band: raster_values[index].reshape(-1).astype(float)
        for index, band in enumerate(RASTER_BANDS)
    }
    projected_points = gpd.GeoDataFrame(
        {
            "grid_row": rows.reshape(-1),
            "grid_col": columns.reshape(-1),
            **values,
        },
        geometry=[
            Point(x, y)
            for x, y in zip(center_x.reshape(-1), center_y.reshape(-1), strict=True)
        ],
        crs=raster_crs,
    )
    boundary = gpd.GeoDataFrame(
        geometry=[area.geometry],
        crs="EPSG:4326",
    ).to_crs(raster_crs)
    try:
        cells = gpd.sjoin(
            projected_points,
            boundary,
            how="inner",
            predicate="within",
        ).drop(columns=["index_right"])
    except (ValueError, TypeError) as exc:
        raise GridProcessingError(
            f"Could not clip raster grid to {area.name}: {exc}"
        ) from exc
    if cells.empty:
        raise GridProcessingError(
            f"The {area.name} boundary contains no cell centers at "
            f"{area.resolution_m} m."
        )

    cells = cells.to_crs("EPSG:4326")
    cells["centroid_lon"] = cells.geometry.x
    cells["centroid_lat"] = cells.geometry.y
    cells["grid_id"] = [
        f"{area.region_id}-{area.resolution_m}-{row:05d}-{column:05d}"
        for row, column in zip(cells.grid_row, cells.grid_col, strict=True)
    ]
    for band in RASTER_BANDS:
        cells[band] = cells[band].where(
            np.isfinite(cells[band]) & (cells[band] != nodata),
            np.nan,
        )
    cells["lst_valid"] = cells["lst_c"].notna()
    cells["ndvi_valid"] = cells["ndvi"].notna()
    cells["ndbi_valid"] = cells["ndbi"].notna()
    cells["ndwi_valid"] = cells["ndwi"].notna()
    cells["population_valid"] = cells["population_estimated_2025"].notna()
    age_denominator = cells["population_age_2020"].where(
        cells["population_age_2020"] > 0
    )
    cells["children_share_2020"] = (
        cells["children_estimated_2020"] / age_denominator
    )
    cells["elderly_share_2020"] = (
        cells["elderly_estimated_2020"] / age_denominator
    )
    cells["data_status"] = np.where(
        cells[
            [
                "lst_valid",
                "ndvi_valid",
                "ndbi_valid",
                "ndwi_valid",
                "population_valid",
            ]
        ].any(axis=1),
        "derived",
        "no_valid_observation",
    )

    created_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "region_id": area.region_id,
        "region_name": area.name,
        "boundary_type": area.boundary_type,
        "boundary_source": area.source,
        "boundary_reference": area.source_reference,
        "boundary_license": area.license,
        "boundary_metadata": area.metadata,
        "boundary_manifest": boundary_manifest,
        "season_year": season_year,
        "season_start": f"{season_year}-04-01",
        "season_end": f"{season_year}-06-30",
        "temporal_composite": "per-pixel seasonal median; spatial mean to grid",
        "resolution_m": area.resolution_m,
        "crs": raster_crs.to_string(),
        "grid_transform": tuple(transform),
        "grid_shape": {"width": width, "height": height},
        "nodata": nodata,
        "scene_counts": scene_counts,
        "acquisition": acquisition,
        "band_names": RASTER_BANDS,
        "sources": {
            "lst_c": "Landsat 8/9 Collection 2 Level 2 L2SP ST_B10",
            "ndvi": "Sentinel-2 SR Harmonized B8/B4",
            "ndbi": "Sentinel-2 SR Harmonized B11/B8",
            "ndwi": "Sentinel-2 SR Harmonized B3/B8",
            "population_estimated_2025": (
                "WorldPop/GP/100m/R2025A/v1/pop; modelled estimate; 3 arc-second "
                "(approximately 100 m) count pixels; CC BY 4.0"
            ),
            "age_structure_2020": (
                "WorldPop/GP/100m/pop_age_sex_cons_unadj; modelled estimate; "
                "CC BY 4.0; older than 2025 total-population estimate"
            ),
        },
        "population_aggregation": {
            "method": (
                "Area-weighted sum of source population counts to the 1 km grid; "
                "source counts are scaled by target/source pixel area before "
                "reduction."
            )
            if area.resolution_m == 1000
            else (
                "WorldPop source values reprojected to the approximately 100 m "
                "grid; no upscaling or within-cell count aggregation."
            ),
            "legacy_cache_corrected_during_processing": population_legacy_corrected,
            "data_status": "derived",
        },
        "weather_join_policy": (
            "Open-Meteo coarse weather is retained by reference location and date, "
            "not downscaled or copied onto individual analysis cells."
        ),
        "data_status": "derived",
        "processing_version": "1.0.1",
        "created_at_utc": created_at,
        "cell_count": int(len(cells)),
        "coverage": {
            column: int(cells[column].sum())
            for column in (
                "lst_valid",
                "ndvi_valid",
                "ndbi_valid",
                "ndwi_valid",
                "population_valid",
            )
        },
    }
    manifest_id = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    manifest["manifest_id"] = manifest_id
    cells["season_year"] = season_year
    cells["resolution_m"] = area.resolution_m
    cells["region_id"] = area.region_id
    cells["manifest_id"] = manifest_id
    columns = [
        "grid_id",
        "manifest_id",
        "region_id",
        "resolution_m",
        "season_year",
        "grid_row",
        "grid_col",
        "centroid_lon",
        "centroid_lat",
        *RASTER_BANDS,
        "lst_valid",
        "ndvi_valid",
        "ndbi_valid",
        "ndwi_valid",
        "population_valid",
        "children_share_2020",
        "elderly_share_2020",
        "data_status",
    ]
    return cells[columns], manifest


def _legacy_worldpop_area_factors(
    transform: rasterio.Affine,
    *,
    height: int,
    raster_crs: rasterio.crs.CRS,
    target_resolution_m: int,
) -> np.ndarray:
    rows = np.arange(height)
    sample_x = np.full(
        height,
        transform.c + 0.5 * transform.a,
        dtype=float,
    )
    sample_y = transform.f + (rows + 0.5) * transform.e
    try:
        _, latitudes = transform_coordinates(
            raster_crs,
            "EPSG:4326",
            sample_x.tolist(),
            sample_y.tolist(),
        )
    except (ValueError, rasterio.errors.RasterioError) as exc:
        raise GridProcessingError(
            f"Could not locate grid rows for WorldPop area correction: {exc}"
        ) from exc

    geod = Geod(ellps="WGS84")
    factors = np.empty(height, dtype=float)
    for row, latitude in enumerate(latitudes):
        factors[row] = worldpop_area_factor(
            float(latitude),
            target_resolution_m=target_resolution_m,
            geod=geod,
        )
    return factors


def worldpop_area_factor(
    latitude: float,
    *,
    target_resolution_m: int,
    geod: Geod | None = None,
) -> float:
    if geod is None:
        geod = Geod(ellps="WGS84")
    half_pixel = WORLDPOP_PIXEL_SIZE_DEGREES / 2
    longitudes = (
        0,
        WORLDPOP_PIXEL_SIZE_DEGREES,
        WORLDPOP_PIXEL_SIZE_DEGREES,
        0,
    )
    latitudes = (
        latitude - half_pixel,
        latitude - half_pixel,
        latitude + half_pixel,
        latitude + half_pixel,
    )
    source_area_m2, _ = geod.polygon_area_perimeter(longitudes, latitudes)
    if not np.isfinite(source_area_m2) or source_area_m2 <= 0:
        raise GridProcessingError(
            f"WorldPop source pixel area is invalid at latitude {latitude}."
        )
    return target_resolution_m**2 / abs(source_area_m2)


def write_grid_csv(frame: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(
        f".{output_path.stem}.{uuid.uuid4().hex}.tmp.csv"
    )
    try:
        frame.to_csv(temporary_path, index=False, na_rep="")
        os.replace(temporary_path, output_path)
    except OSError as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError as cleanup_error:
            raise GridProcessingError(
                f"Could not write {output_path.name}, and the temporary file "
                f"could not be removed: {cleanup_error}"
            ) from exc
        raise GridProcessingError(f"Could not write grid CSV {output_path.name}: {exc}") from exc


def write_grid_geojson(
    frame: pd.DataFrame,
    output_path: Path,
    *,
    resolution_m: int,
) -> None:
    if resolution_m not in (100, 1000):
        raise ValueError("analysis resolution must be 100 m or 1000 m")
    temporary_path = output_path.with_name(
        f".{output_path.stem}.{uuid.uuid4().hex}.tmp.geojson"
    )
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        projected = gpd.GeoDataFrame(
            frame.drop(columns=["geometry"]),
            geometry=frame.geometry,
            crs="EPSG:4326",
        ).to_crs("EPSG:32644")
        half_cell = resolution_m / 2
        polygons = [
            box(
                point.x - half_cell,
                point.y - half_cell,
                point.x + half_cell,
                point.y + half_cell,
            )
            for point in projected.geometry
        ]
        cells = gpd.GeoDataFrame(
            projected.drop(columns=["geometry"]),
            geometry=polygons,
            crs="EPSG:32644",
        ).to_crs("EPSG:4326")
        cells.to_file(temporary_path, driver="GeoJSON")
        os.replace(temporary_path, output_path)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError as cleanup_error:
            raise GridProcessingError(
                f"Could not write {output_path.name}, and the temporary file "
                f"could not be removed: {cleanup_error}"
            ) from exc
        raise GridProcessingError(
            f"Could not write grid GeoJSON {output_path.name}: {exc}"
        ) from exc
