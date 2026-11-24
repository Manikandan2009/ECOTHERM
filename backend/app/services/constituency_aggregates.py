import hashlib
import json
import re
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd

from app.services.grid_processing import GridProcessingError


SOURCE = "DataMeet India community, github.com/datameet/maps"
SOURCE_URL = "https://github.com/datameet/maps"
LICENSE = "Creative Commons Attribution 4.0 International (CC BY 4.0)"
DELIMITATION_YEAR = "2008"
AREA_CRS = "EPSG:6933"


def prepare_constituency_boundaries(cache_dir: Path) -> dict[str, Any]:
    boundary_dir = cache_dir / "processed" / "boundaries"
    source_path = boundary_dir / "India_AC.shp"
    required_files = [
        source_path,
        source_path.with_suffix(".shx"),
        source_path.with_suffix(".dbf"),
        source_path.with_suffix(".prj"),
    ]
    missing_files = [str(path) for path in required_files if not path.is_file()]
    if missing_files:
        raise GridProcessingError(
            "The India_AC shapefile is incomplete; missing: "
            + ", ".join(missing_files)
        )

    try:
        source = gpd.read_file(source_path)
        districts = gpd.read_file(boundary_dir / "districts.geojson")
    except (OSError, ValueError) as exc:
        raise GridProcessingError(f"Could not read constituency boundaries: {exc}") from exc

    required_columns = {"ST_NAME", "AC_NO", "AC_NAME", "geometry"}
    if not required_columns.issubset(source.columns):
        raise GridProcessingError(
            "India_AC is missing required fields: "
            + ", ".join(sorted(required_columns - set(source.columns)))
        )
    if "district_id" not in districts or "district_name" not in districts:
        raise GridProcessingError("District boundaries lack district IDs or names.")

    tamil_nadu = source[
        source["ST_NAME"].astype(str).str.strip().str.casefold().eq("tamil nadu")
    ].copy()
    tamil_nadu["ac_no"] = pd.to_numeric(tamil_nadu["AC_NO"], errors="coerce")
    if tamil_nadu["ac_no"].isna().any() or (
        tamil_nadu["ac_no"] % 1 != 0
    ).any():
        raise GridProcessingError("Tamil Nadu constituency numbers are missing or invalid.")
    tamil_nadu["ac_no"] = tamil_nadu["ac_no"].astype(int)
    tamil_nadu["constituency_name"] = (
        tamil_nadu["AC_NAME"].fillna("").astype(str).str.strip()
    )

    if len(tamil_nadu) != 234:
        raise GridProcessingError(
            f"Expected exactly 234 Tamil Nadu constituency records; found {len(tamil_nadu)}."
        )
    if tamil_nadu["ac_no"].nunique() != 234:
        duplicates = (
            tamil_nadu.loc[tamil_nadu["ac_no"].duplicated(keep=False), "ac_no"]
            .astype(str)
            .tolist()
        )
        raise GridProcessingError(
            "Tamil Nadu constituency numbers are not unique: "
            + ", ".join(sorted(set(duplicates)))
        )
    missing_names = tamil_nadu.loc[
        tamil_nadu["constituency_name"].eq(""), "ac_no"
    ].astype(int).tolist()
    if missing_names:
        raise GridProcessingError(
            "Tamil Nadu constituencies have missing names for AC numbers: "
            + ", ".join(map(str, missing_names))
        )

    districts = districts.to_crs(AREA_CRS)
    tamil_nadu = tamil_nadu.to_crs(AREA_CRS)
    district_rows = list(districts.itertuples(index=False))
    records: list[dict[str, Any]] = []
    low_overlap: list[dict[str, Any]] = []

    for row in tamil_nadu.itertuples(index=False):
        geometry = row.geometry
        if geometry is None or geometry.is_empty or geometry.area <= 0:
            raise GridProcessingError(
                f"Constituency {row.ac_no} ({row.constituency_name}) has no usable geometry."
            )
        overlap_candidates = [
            (
                geometry.intersection(district.geometry).area,
                str(district.district_id),
                str(district.district_name),
            )
            for district in district_rows
        ]
        largest_overlap, district_id, district_name = max(
            overlap_candidates,
            key=lambda item: item[0],
        )
        if largest_overlap <= 0:
            raise GridProcessingError(
                f"Constituency {row.ac_no} ({row.constituency_name}) "
                "does not intersect a Tamil Nadu district."
            )
        overlap_percent = largest_overlap / geometry.area * 100
        slug = re.sub(
            r"[^a-z0-9]+",
            "_",
            row.constituency_name.casefold(),
        ).strip("_")
        constituency_id = f"ac_{int(row.ac_no):03d}_{slug}"
        records.append(
            {
                "constituency_id": constituency_id,
                "constituency_name": row.constituency_name,
                "ac_number": int(row.ac_no),
                "district_id": district_id,
                "district_name": district_name,
                "parent_district_overlap_percent": overlap_percent,
                "source": SOURCE,
                "source_reference": SOURCE_URL,
                "license": LICENSE,
                "delimitation_year": DELIMITATION_YEAR,
                "geometry": geometry,
            }
        )
        if overlap_percent < 80:
            low_overlap.append(
                {
                    "ac_number": int(row.ac_no),
                    "constituency_name": row.constituency_name,
                    "district_name": district_name,
                    "overlap_percent": round(overlap_percent, 2),
                }
            )

    prepared = gpd.GeoDataFrame(records, crs=AREA_CRS).to_crs("EPSG:4326")
    prepared = prepared.sort_values(
        ["district_name", "constituency_name", "ac_number"],
        kind="stable",
    ).reset_index(drop=True)
    duplicate_names = sorted(
        name
        for name, count in prepared["constituency_name"].value_counts().items()
        if count > 1
    )
    name_quality_issues = [
        {
            "ac_number": int(row.ac_number),
            "constituency_name": str(row.constituency_name),
            "issue": "unbalanced_parentheses_in_source_name",
        }
        for row in prepared.itertuples(index=False)
        if str(row.constituency_name).count("(")
        != str(row.constituency_name).count(")")
    ]
    prepared["parent_district_overlap_percent"] = prepared[
        "parent_district_overlap_percent"
    ].round(2)

    output_path = boundary_dir / "constituencies.geojson"
    try:
        prepared.to_file(output_path, driver="GeoJSON")
    except (OSError, ValueError) as exc:
        raise GridProcessingError(
            f"Could not write cached constituency GeoJSON: {exc}"
        ) from exc

    manifest = {
        "boundary_type": "assembly_constituency",
        "constituency_count": len(prepared),
        "state_filter": "ST_NAME = Tamil Nadu",
        "source": SOURCE,
        "source_reference": SOURCE_URL,
        "license": LICENSE,
        "delimitation_year": DELIMITATION_YEAR,
        "source_shapefile": "India_AC.shp",
        "district_assignment": (
            "Largest polygon-area overlap with the cached 2021 district boundaries "
            "measured in EPSG:6933."
        ),
        "district_boundary_year": "2021",
        "feature_count": len(prepared),
        "unique_ac_number_count": int(prepared["ac_number"].nunique()),
        "missing_name_ac_numbers": missing_names,
        "duplicate_names": duplicate_names,
        "district_overlap_below_80_percent": low_overlap,
        "generated_from_source_features": len(tamil_nadu),
    }
    manifest["boundary_manifest_id"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    manifest["name_quality_issues"] = name_quality_issues
    manifest_path = boundary_dir / "constituencies_manifest.json"
    _write_json(manifest_path, manifest)
    _update_source_manifest(boundary_dir, manifest)
    return manifest


def cache_constituency_static_batches(
    *,
    cache_dir: Path,
    season_year: int,
    batch_size: int = 30,
    start_batch: int = 1,
    force_refresh: bool = False,
) -> dict[str, Any]:
    if batch_size != 30:
        raise GridProcessingError("Constituency cache batches must contain 30 features.")
    if start_batch < 1:
        raise GridProcessingError("Constituency start batch must be at least 1.")

    boundary_dir = cache_dir / "processed" / "boundaries"
    try:
        boundaries = gpd.read_file(boundary_dir / "constituencies.geojson")
        manifest = json.loads(
            (boundary_dir / "constituencies_manifest.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise GridProcessingError(
            "Prepare and validate constituency boundaries before caching data."
        ) from exc
    if len(boundaries) != 234:
        raise GridProcessingError(
            f"Expected 234 cached constituency polygons; found {len(boundaries)}."
        )
    grid_path = (
        cache_dir
        / "processed"
        / "grids"
        / f"tamil_nadu_1000m_{season_year}.csv"
    )
    if not grid_path.is_file():
        raise GridProcessingError(
            "Constituency caching requires the cached Tamil Nadu 1 km grid CSV."
        )

    grid = pd.read_csv(grid_path)
    required_grid_columns = {
        "grid_id",
        "centroid_lon",
        "centroid_lat",
        "lst_c",
        "ndvi",
        "ndbi",
        "population_estimated_2025",
    }
    if not required_grid_columns.issubset(grid.columns):
        raise GridProcessingError(
            "The statewide grid lacks required aggregation columns: "
            + ", ".join(sorted(required_grid_columns - set(grid.columns)))
        )
    cells = gpd.GeoDataFrame(
        grid,
        geometry=gpd.points_from_xy(grid.centroid_lon, grid.centroid_lat),
        crs="EPSG:4326",
    )
    output_root = cache_dir / "processed" / "constituencies" / "static_batches"
    output_root.mkdir(parents=True, exist_ok=True)
    ordered = boundaries.sort_values(
        ["district_name", "constituency_name", "ac_number"],
        kind="stable",
    ).reset_index(drop=True)
    batches: list[dict[str, Any]] = []
    selected_batch = ordered.iloc[(start_batch - 1) * 30 : start_batch * 30]
    if selected_batch.empty:
        raise GridProcessingError(f"Constituency batch {start_batch} does not exist.")

    matched = gpd.sjoin(
        cells,
        selected_batch[["constituency_id", "geometry"]],
        how="inner",
        predicate="within",
    )
    for row in selected_batch.itertuples(index=False):
        output_dir = output_root / row.constituency_id
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / f"{row.constituency_id}_{season_year}.csv"
        geojson_path = output_dir / f"{row.constituency_id}_{season_year}.geojson"
        manifest_path = output_dir / "manifest.json"
        if not force_refresh and all(
            path.is_file() for path in (csv_path, geojson_path, manifest_path)
        ):
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if existing.get("boundary_manifest_id") == manifest.get(
                "boundary_manifest_id"
            ):
                batches.append(
                    {
                        "constituency_id": row.constituency_id,
                        "constituency_name": row.constituency_name,
                        "district_name": row.district_name,
                        "status": "cached",
                        "grid_cell_count": existing.get("grid_cell_count"),
                    }
                )
                continue

        selected_cells = matched[
            matched["constituency_id"].eq(row.constituency_id)
        ].drop(columns=["index_right", "geometry"], errors="ignore")
        selected_cells.to_csv(csv_path, index=False)
        summary = _summarize_constituency(selected_cells)
        feature_properties = {
            "constituency_id": row.constituency_id,
            "constituency_name": row.constituency_name,
            "ac_number": int(row.ac_number),
            "district_id": row.district_id,
            "district_name": row.district_name,
            "parent_district_overlap_percent": float(
                row.parent_district_overlap_percent
            ),
            **summary,
            "season_year": season_year,
            "lst_composite_start": f"{season_year}-04-01",
            "lst_composite_end": f"{season_year}-06-30",
            "population_source_year": 2025,
            "population_status": "estimated/modelled WorldPop, 2025",
            "source": SOURCE,
            "license": LICENSE,
            "delimitation_year": DELIMITATION_YEAR,
        }
        feature = gpd.GeoDataFrame(
            [dict(feature_properties, geometry=row.geometry)],
            crs="EPSG:4326",
        )
        feature.to_file(geojson_path, driver="GeoJSON")
        cache_manifest = {
            **feature_properties,
            "boundary_manifest_id": manifest.get("boundary_manifest_id"),
            "data_status": "derived",
            "input_grid": f"tamil_nadu_1000m_{season_year}.csv",
            "input_resolution_m": 1000,
            "aggregation_method": (
                "Assign cached statewide 1 km cell centers within the constituency; "
                "no satellite acquisition or raster resampling was performed."
            ),
            "data_gaps": (
                [] if summary["grid_cell_count"] else ["No cached grid cell centers."]
            ),
        }
        _write_json(manifest_path, cache_manifest)
        batches.append(
            {
                "constituency_id": row.constituency_id,
                "constituency_name": row.constituency_name,
                "district_name": row.district_name,
                "status": "created",
                "grid_cell_count": summary["grid_cell_count"],
                "lst_mean_c": summary["lst_mean_c"],
                "population_estimated_2025": summary[
                    "population_estimated_2025"
                ],
            }
        )

    batch_output = {
        "status": "complete",
        "batch": start_batch,
        "batch_size": batch_size,
        "constituency_count": len(selected_batch),
        "season_year": season_year,
        "constituencies": batches,
    }
    batch_manifest_dir = cache_dir / "processed" / "constituencies"
    batch_manifest_dir.mkdir(parents=True, exist_ok=True)
    _write_json(batch_manifest_dir / f"batch_{start_batch:02d}_manifest.json", batch_output)
    return batch_output


def _summarize_constituency(cells: pd.DataFrame) -> dict[str, Any]:
    cell_count = int(len(cells))
    valid_lst = pd.to_numeric(cells["lst_c"], errors="coerce").dropna()
    population = pd.to_numeric(
        cells["population_estimated_2025"], errors="coerce"
    )
    valid_population_count = int(population.notna().sum())
    valid_population_sum = population.sum(min_count=1)
    result: dict[str, Any] = {
        "grid_cell_count": cell_count,
        "lst_valid_cell_count": int(valid_lst.size),
        "lst_coverage_percent": (
            float(valid_lst.size / cell_count * 100) if cell_count else None
        ),
        "lst_mean_c": float(valid_lst.mean()) if not valid_lst.empty else None,
        "lst_max_c": float(valid_lst.max()) if not valid_lst.empty else None,
        "population_valid_cell_count": valid_population_count,
        "population_coverage_percent": (
            float(valid_population_count / cell_count * 100) if cell_count else None
        ),
        "population_estimated_2025": (
            float(valid_population_sum)
            if pd.notna(valid_population_sum)
            else None
        ),
        "people_exposed_high_heat": None,
        "high_risk_cell_count": None,
        "risk_score_mean": None,
        "risk_score_max": None,
    }
    if cell_count == 0:
        return result

    evidence = cells[
        ["lst_c", "ndvi", "ndbi", "population_estimated_2025"]
    ].replace([np.inf, -np.inf], np.nan).dropna()
    if evidence.empty:
        return result
    exposure = evidence["lst_c"].rank(pct=True).mul(100).clip(0, 100)
    low_vegetation = (
        ((0.4 - evidence["ndvi"]).clip(-0.6, 0.6) + 0.6) / 1.2 * 100
    ).clip(0, 100)
    built_up = evidence["ndbi"].clip(-1, 1).add(1).div(2).mul(100)
    density_cap = evidence["population_estimated_2025"].quantile(0.95)
    if pd.notna(density_cap) and density_cap > 0:
        density = (
            evidence["population_estimated_2025"]
            .div(density_cap)
            .mul(100)
            .clip(0, 100)
        )
    else:
        density = pd.Series(0, index=evidence.index)
    vulnerability = (
        low_vegetation.mul(0.4) + built_up.mul(0.35) + density.mul(0.25)
    ).clip(0, 100)
    risk = exposure.mul(vulnerability).div(100).clip(0, 100)
    high_risk = risk >= 75
    result.update(
        {
            "people_exposed_high_heat": float(
                evidence.loc[
                    high_risk, "population_estimated_2025"
                ].sum()
            ),
            "high_risk_cell_count": int(high_risk.sum()),
            "risk_score_mean": float(risk.mean()),
            "risk_score_max": float(risk.max()),
        }
    )
    return result


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _update_source_manifest(
    boundary_dir: Path,
    constituency_manifest: dict[str, Any],
) -> None:
    source_manifest_path = boundary_dir / "source_manifest.json"
    try:
        source_manifest = json.loads(
            source_manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise GridProcessingError(
            f"Could not update boundary source manifest: {exc}"
        ) from exc
    source_manifest["constituencies"] = {
        key: constituency_manifest[key]
        for key in (
            "boundary_type",
            "constituency_count",
            "source",
            "source_reference",
            "license",
            "delimitation_year",
            "source_shapefile",
            "district_assignment",
            "district_boundary_year",
            "duplicate_names",
            "missing_name_ac_numbers",
            "district_overlap_below_80_percent",
            "name_quality_issues",
        )
    }
    _write_json(source_manifest_path, source_manifest)
