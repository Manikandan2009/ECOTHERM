import json
import os
import uuid
import hashlib
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from app.services.grid_processing import GridProcessingError


DISTRICT_SUMMARY_COLUMNS = (
    "district_id",
    "district_name",
    "season_year",
    "cell_count",
    "lst_valid_cells",
    "lst_coverage_pct",
    "lst_mean_c",
    "lst_max_c",
    "ndvi_valid_cells",
    "ndvi_mean",
    "ndbi_mean",
    "ndwi_mean",
    "population_valid_cells",
    "population_estimated_2025",
    "population_age_2020",
    "children_estimated_2020",
    "elderly_estimated_2020",
    "children_share_2020",
    "elderly_share_2020",
    "data_status",
)


def cache_district_static_batches(
    *,
    cache_dir: Path,
    season_year: int,
    batch_size: int = 4,
    start_batch: int = 1,
    force_refresh: bool = False,
) -> dict[str, object]:
    if batch_size < 1:
        raise GridProcessingError("District batch size must be at least 1.")
    if start_batch < 1:
        raise GridProcessingError("District start batch must be at least 1.")
    districts = gpd.read_file(
        cache_dir / "processed" / "boundaries" / "districts.geojson"
    )
    state_grid_path = (
        cache_dir / "processed" / "grids"
        / f"tamil_nadu_1000m_{season_year}.csv"
    )
    if districts.empty or not state_grid_path.is_file():
        raise GridProcessingError(
            "District static caching requires district GeoJSON and the "
            "cached Tamil Nadu grid CSV."
        )
    districts = districts.to_crs("EPSG:4326")
    state_grid = pd.read_csv(state_grid_path)
    cells = gpd.GeoDataFrame(
        state_grid,
        geometry=gpd.points_from_xy(
            state_grid.centroid_lon,
            state_grid.centroid_lat,
        ),
        crs="EPSG:4326",
    )
    output_root = cache_dir / "processed" / "districts"
    cache_directory = output_root / "static_batches"
    cache_directory.mkdir(parents=True, exist_ok=True)

    district_rows = districts[
        ["district_id", "district_name", "source",
         "source_reference", "license", "boundary_year", "geometry"]
    ].copy()
    district_rows = district_rows.sort_values("district_name")
    batches: list[dict[str, object]] = []
    cached_count = 0
    for start in range(0, len(district_rows), batch_size):
        batch = district_rows.iloc[start:start + batch_size]
        batch_number = start // batch_size + 1
        if batch_number < start_batch:
            continue
        if batch_number != start_batch:
            continue
        batch_result: list[dict[str, object]] = []
        for district in batch.itertuples(index=False):
            district_id = district.district_id
            district_directory = cache_directory / district_id
            district_directory.mkdir(parents=True, exist_ok=True)
            csv_path = district_directory / f"{district_id}_{season_year}.csv"
            geojson_path = district_directory / f"{district_id}_{season_year}.geojson"
            manifest_path = district_directory / "manifest.json"

            if (
                not force_refresh
                and csv_path.is_file()
                and geojson_path.is_file()
                and manifest_path.is_file()
            ):
                cached_count += 1
                batch_result.append({
                    "district_id": district_id,
                    "district_name": district.district_name,
                    "status": "cached",
                    "csv": str(csv_path),
                    "geojson": str(geojson_path),
                })
                continue

            matched = gpd.sjoin(
                cells,
                gpd.GeoDataFrame(
                    [{"district_id": district_id, "geometry": district.geometry}],
                    crs="EPSG:4326",
                ),
                how="inner",
                predicate="within",
            )
            if matched.empty:
                batch_result.append({
                    "district_id": district_id,
                    "district_name": district.district_name,
                    "status": "unavailable",
                    "reason": "No cached 1 km cell centers are within the district boundary.",
                })
                continue
            district_cells = matched.drop(columns=["index_right"], errors="ignore")
            district_cells = district_cells.drop(columns=["geometry"])
            district_cells.to_csv(csv_path, index=False)

            valid_lst = district_cells["lst_c"].dropna()
            population = district_cells["population_estimated_2025"].sum(min_count=1)
            summary = {
                "district_id": district_id,
                "district_name": district.district_name,
                "season_year": season_year,
                "lst_composite_start": f"{season_year}-04-01",
                "lst_composite_end": f"{season_year}-06-30",
                "lst_mean_c": float(valid_lst.mean()) if len(valid_lst) else None,
                "lst_max_c": float(valid_lst.max()) if len(valid_lst) else None,
                "lst_valid_cells": int(len(valid_lst)),
                "cell_count": int(len(district_cells)),
                "worldpop_population_2025": (
                    float(population) if pd.notna(population) else None
                ),
                "worldpop_population_year": 2025,
                "population_valid_cells": int(
                    district_cells["population_valid"].sum()
                    if "population_valid" in district_cells
                    else district_cells["population_estimated_2025"].notna().sum()
                ),
                "source": district.source,
                "source_reference": district.source_reference,
                "license": district.license,
                "boundary_year": district.boundary_year,
            }
            feature = gpd.GeoDataFrame(
                [dict(summary, geometry=district.geometry)],
                crs="EPSG:4326",
            )
            feature.to_file(geojson_path, driver="GeoJSON")
            manifest_payload = dict(
                summary,
                data_status="cached",
                lst_status="observed/derived Landsat seasonal median",
                population_status="estimated/modelled WorldPop",
                processing_version="district-static-batch-v1",
            )
            manifest_payload["manifest_id"] = hashlib.sha256(
                json.dumps(manifest_payload, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest_payload, indent=2, default=str),
                encoding="utf-8",
            )
            batch_result.append({
                "district_id": district_id,
                "district_name": district.district_name,
                "status": "created",
                "csv": str(csv_path),
                "geojson": str(geojson_path),
                "lst_mean_c": summary["lst_mean_c"],
                "worldpop_population_2025": summary["worldpop_population_2025"],
            })
        batches.append({
            "batch": batch_number,
            "district_count": len(batch_result),
            "districts": batch_result,
        })

    return {
        "status": "complete",
        "season_year": season_year,
        "batch_size": batch_size,
        "district_count": len(district_rows),
        "already_cached": cached_count,
        "batches": batches,
    }


def aggregate_grid_to_districts(
    grid_records: pd.DataFrame,
    districts: gpd.GeoDataFrame,
    *,
    season_year: int,
) -> pd.DataFrame:
    if grid_records.empty or districts.empty:
        raise GridProcessingError(
            "District aggregation requires non-empty grid records and boundaries."
        )
    cells = gpd.GeoDataFrame(
        grid_records.copy(),
        geometry=gpd.points_from_xy(
            grid_records.centroid_lon,
            grid_records.centroid_lat,
        ),
        crs="EPSG:4326",
    )
    try:
        matched = gpd.sjoin(
            cells,
            districts[["district_id", "district_name", "geometry"]],
            how="inner",
            predicate="within",
        )
    except (ValueError, TypeError) as exc:
        raise GridProcessingError(f"Could not assign grid cells to districts: {exc}") from exc
    if matched.empty:
        raise GridProcessingError("No Tamil Nadu grid cells intersect district boundaries.")

    summaries: list[dict[str, object]] = []
    for (district_id, district_name), group in matched.groupby(
        ["district_id", "district_name"],
        sort=True,
    ):
        valid_lst = group["lst_c"].dropna()
        valid_ndvi = group["ndvi"].dropna()
        age_population = group["population_age_2020"].sum(min_count=1)
        children = group["children_estimated_2020"].sum(min_count=1)
        elderly = group["elderly_estimated_2020"].sum(min_count=1)
        summaries.append(
            {
                "district_id": district_id,
                "district_name": district_name,
                "season_year": season_year,
                "cell_count": len(group),
                "lst_valid_cells": len(valid_lst),
                "lst_coverage_pct": (
                    len(valid_lst) / len(group) * 100 if len(group) else None
                ),
                "lst_mean_c": valid_lst.mean() if len(valid_lst) else np.nan,
                "lst_max_c": valid_lst.max() if len(valid_lst) else np.nan,
                "ndvi_valid_cells": len(valid_ndvi),
                "ndvi_mean": valid_ndvi.mean() if len(valid_ndvi) else np.nan,
                "ndbi_mean": group["ndbi"].mean(),
                "ndwi_mean": group["ndwi"].mean(),
                "population_valid_cells": int(group["population_valid"].sum()),
                "population_estimated_2025": group[
                    "population_estimated_2025"
                ].sum(min_count=1),
                "population_age_2020": age_population,
                "children_estimated_2020": children,
                "elderly_estimated_2020": elderly,
                "children_share_2020": (
                    children / age_population
                    if pd.notna(children) and pd.notna(age_population) and age_population > 0
                    else np.nan
                ),
                "elderly_share_2020": (
                    elderly / age_population
                    if pd.notna(elderly) and pd.notna(age_population) and age_population > 0
                    else np.nan
                ),
                "data_status": "derived",
            }
        )
    return pd.DataFrame(summaries, columns=DISTRICT_SUMMARY_COLUMNS)


def write_district_outputs(
    summary: pd.DataFrame,
    districts: gpd.GeoDataFrame,
    output_directory: Path,
) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    csv_path = output_directory / "district_summary.csv"
    temporary_path = csv_path.with_name(
        f".{csv_path.stem}.{uuid.uuid4().hex}.tmp.csv"
    )
    try:
        summary.to_csv(temporary_path, index=False, na_rep="")
        os.replace(temporary_path, csv_path)
    except OSError as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError as cleanup_error:
            raise GridProcessingError(
                f"District CSV write failed and temporary file cleanup failed: "
                f"{cleanup_error}"
            ) from exc
        raise GridProcessingError(f"Could not write district summary: {exc}") from exc

    geojson_path = output_directory / "district_summary.geojson"
    boundary_summary = districts.merge(
        summary,
        on=["district_id", "district_name"],
        how="left",
        validate="one_to_one",
    )
    boundary_summary.to_file(geojson_path, driver="GeoJSON")
    (output_directory / "district_summary_manifest.json").write_text(
        json.dumps(
            {
                "data_status": "derived",
                "aggregation_method": (
                    "1 km cell-center assignment to 2021 district polygons; "
                    "population is WorldPop modelled estimate"
                ),
                "district_count_with_grid_data": int(summary.district_id.nunique()),
                "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return csv_path, geojson_path
