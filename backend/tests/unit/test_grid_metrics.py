import os

import pandas as pd
import pytest

from app.repositories import grid_metrics
from app.repositories.grid_exports import GridExportError


@pytest.fixture(autouse=True)
def clear_metrics_cache():
    grid_metrics.clear_grid_export_metrics_cache()
    yield
    grid_metrics.clear_grid_export_metrics_cache()


def _write_grid(path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_grid_metrics_share_one_parsed_export_across_summaries(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "processed" / "grids" / "tamil_nadu_1000m_2026.csv"
    _write_grid(
        path,
        [
            {
                "region_id": "tamil_nadu",
                "season_year": 2026,
                "resolution_m": 1000,
                "lst_c": 40.0,
                "ndvi": 0.4,
                "ndbi": 0.1,
                "ndwi": -0.2,
                "population_estimated_2025": 100.0,
            },
            {
                "region_id": "tamil_nadu",
                "season_year": 2026,
                "resolution_m": 1000,
                "lst_c": 42.0,
                "ndvi": 0.6,
                "ndbi": None,
                "ndwi": -0.4,
                "population_estimated_2025": 200.0,
            },
        ],
    )
    read_count = 0
    original_read_csv = pd.read_csv

    def counting_read_csv(*args, **kwargs):
        nonlocal read_count
        read_count += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(grid_metrics.pd, "read_csv", counting_read_csv)
    all_columns = (
        "lst_c",
        "ndvi",
        "ndbi",
        "ndwi",
        "population_estimated_2025",
    )
    summary = grid_metrics.read_grid_export_metrics(
        tmp_path,
        region_id="tamil_nadu",
        season_year=2026,
        resolution_m=1000,
        columns=all_columns,
        required_columns=all_columns,
    )
    satellite = grid_metrics.read_grid_export_metrics(
        tmp_path,
        region_id="tamil_nadu",
        season_year=2026,
        resolution_m=1000,
        columns=("lst_c", "ndvi", "ndbi", "ndwi"),
        required_columns=("lst_c", "ndvi", "ndbi", "ndwi"),
    )

    assert summary is satellite
    assert summary is not None
    assert summary.grid_cell_count == 2
    assert summary.lst is not None and summary.lst.mean == 41.0
    assert summary.ndvi is not None and summary.ndvi.valid_cell_count == 2
    assert summary.ndbi is not None and summary.ndbi.valid_cell_count == 1
    assert summary.population_valid_cell_count == 2
    assert summary.estimated_population_2025 == 300.0
    assert summary.people_exposed_high_heat is not None
    assert summary.high_risk_cell_count is not None
    assert read_count == 1


def test_grid_metrics_invalidate_when_file_version_changes(tmp_path) -> None:
    path = tmp_path / "processed" / "grids" / "tamil_nadu_1000m_2026.csv"
    columns = ("lst_c", "population_estimated_2025")
    _write_grid(
        path,
        [{"lst_c": 40.0, "population_estimated_2025": 100.0}],
    )
    first = grid_metrics.read_grid_export_metrics(
        tmp_path,
        region_id="tamil_nadu",
        season_year=2026,
        resolution_m=1000,
        columns=columns,
        required_columns=columns,
    )
    stat = path.stat()
    _write_grid(
        path,
        [{"lst_c": 50.0, "population_estimated_2025": 100.0}],
    )
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))

    updated = grid_metrics.read_grid_export_metrics(
        tmp_path,
        region_id="tamil_nadu",
        season_year=2026,
        resolution_m=1000,
        columns=columns,
        required_columns=columns,
    )

    assert first is not None and first.lst is not None and first.lst.mean == 40.0
    assert updated is not None and updated.lst is not None and updated.lst.mean == 50.0


def test_grid_metrics_reject_mismatched_metadata_and_missing_columns(tmp_path) -> None:
    path = tmp_path / "processed" / "grids" / "tamil_nadu_1000m_2026.csv"
    _write_grid(
        path,
        [
            {
                "region_id": "other_region",
                "season_year": 2026,
                "resolution_m": 1000,
                "lst_c": 40.0,
                "population_estimated_2025": 100.0,
            }
        ],
    )

    with pytest.raises(GridExportError, match="mismatched region"):
        grid_metrics.read_grid_export_metrics(
            tmp_path,
            region_id="tamil_nadu",
            season_year=2026,
            resolution_m=1000,
            columns=("lst_c", "population_estimated_2025"),
            required_columns=("lst_c", "population_estimated_2025"),
        )
    _write_grid(path, [{"lst_c": 40.0}])
    with pytest.raises(GridExportError, match="missing columns"):
        grid_metrics.read_grid_export_metrics(
            tmp_path,
            region_id="tamil_nadu",
            season_year=2026,
            resolution_m=1000,
            columns=("lst_c", "population_estimated_2025"),
            required_columns=("lst_c", "population_estimated_2025"),
        )


def test_region_csv_metrics_share_reads_and_respect_ndvi_validity(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "districts" / "alpha_2026.csv"
    _write_grid(
        path,
        [
            {
                "lst_c": 40.0,
                "ndvi": 0.2,
                "ndvi_valid": True,
                "ndbi": 0.3,
                "population_estimated_2025": 100.0,
            },
            {
                "lst_c": 50.0,
                "ndvi": 0.8,
                "ndvi_valid": False,
                "ndbi": 0.3,
                "population_estimated_2025": 100.0,
            },
        ],
    )
    read_count = 0
    original_read_csv = pd.read_csv

    def counting_read_csv(*args, **kwargs):
        nonlocal read_count
        read_count += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(grid_metrics.pd, "read_csv", counting_read_csv)
    first = grid_metrics.read_region_csv_metrics(path, include_heat_risk=True)
    second = grid_metrics.read_region_csv_metrics(path, include_heat_risk=True)

    assert first is second
    assert first is not None
    assert first.ndvi_mean == 0.2
    assert first.people_exposed_high_heat is not None
    assert first.high_risk_cell_count is not None
    assert read_count == 1

    _write_grid(
        path,
        [
            {
                "lst_c": 40.0,
                "ndvi": 0.5,
                "ndvi_valid": True,
                "ndbi": 0.3,
                "population_estimated_2025": 100.0,
            },
        ],
    )
    updated = grid_metrics.read_region_csv_metrics(path, include_heat_risk=True)
    assert updated is not None and updated.ndvi_mean == 0.5
    assert read_count == 2
