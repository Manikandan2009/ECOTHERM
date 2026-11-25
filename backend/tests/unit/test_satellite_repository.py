import sqlite3

import pytest

from app.repositories.satellite import (
    load_constituency_scatter,
    load_satellite_summary,
)


def _create_grid_database(database_path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE grid_observations (
                region_id TEXT,
                season_year INTEGER,
                resolution_m INTEGER,
                lst_c REAL,
                ndvi REAL,
                ndbi REAL,
                ndwi REAL
            )
            """
        )


def test_satellite_summary_reports_cached_means_and_layer_coverage(tmp_path) -> None:
    database_path = tmp_path / "ecotherm.sqlite"
    _create_grid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            "INSERT INTO grid_observations VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("tamil_nadu", 2026, 1000, 40.0, 0.4, 0.1, -0.2),
                ("tamil_nadu", 2026, 1000, 42.0, 0.6, None, -0.4),
                ("chennai", 2026, 100, 38.0, 0.8, 0.2, 0.1),
            ],
        )

    summary = load_satellite_summary(
        database_path,
        region_id="tamil_nadu",
        season_year=2026,
    )

    assert summary.data_status == "available"
    assert summary.grid_cell_count == 2
    assert summary.grid_resolution_m == 1000
    assert summary.lst.mean == pytest.approx(41.0)
    assert summary.lst.coverage_percent == 100
    assert summary.ndvi.mean == pytest.approx(0.5)
    assert summary.ndvi.valid_cell_count == 2
    assert summary.ndbi.mean == pytest.approx(0.1)
    assert summary.ndbi.coverage_percent == 50
    assert summary.ndwi.mean == pytest.approx(-0.3)
    assert summary.composite_start == "2026-04-01"
    assert summary.composite_end == "2026-06-30"


def test_satellite_summary_prefers_cached_grid_csv(tmp_path) -> None:
    database_path = tmp_path / "processed" / "ecotherm.sqlite"
    database_path.parent.mkdir(parents=True)
    _create_grid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO grid_observations VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("tamil_nadu", 2026, 1000, 20.0, -0.5, -0.5, -0.5),
        )
    grid_directory = tmp_path / "processed" / "grids"
    grid_directory.mkdir()
    (grid_directory / "tamil_nadu_1000m_2026.csv").write_text(
        "region_id,season_year,resolution_m,lst_c,ndvi,ndbi,ndwi\n"
        "tamil_nadu,2026,1000,40,0.4,0.1,-0.2\n"
        "tamil_nadu,2026,1000,42,0.6,, -0.4\n",
        encoding="utf-8",
    )

    summary = load_satellite_summary(
        database_path,
        region_id="tamil_nadu",
        season_year=2026,
        cache_dir=tmp_path,
    )

    assert summary.grid_cell_count == 2
    assert summary.lst.mean == pytest.approx(41)
    assert summary.ndvi.mean == pytest.approx(0.5)
    assert summary.ndbi.coverage_percent == 50


def test_satellite_summary_keeps_missing_regions_unavailable(tmp_path) -> None:
    database_path = tmp_path / "ecotherm.sqlite"
    _create_grid_database(database_path)

    summary = load_satellite_summary(
        database_path,
        region_id="district_not_cached",
        season_year=2026,
    )

    assert summary.data_status == "unavailable"
    assert summary.grid_cell_count is None
    assert summary.ndvi.mean is None
    assert summary.ndvi.coverage_percent is None
    assert summary.composite_start is None


def test_constituency_satellite_summary_uses_cached_grid_when_database_has_no_rows(
    tmp_path,
) -> None:
    database_path = tmp_path / "ecotherm.sqlite"
    _create_grid_database(database_path)
    constituency_id = "ac_001_gummidipoondi"
    directory = (
        tmp_path
        / "processed"
        / "constituencies"
        / "static_batches"
        / constituency_id
    )
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        '{"constituency_id":"ac_001_gummidipoondi","season_year":2026,'
        '"input_resolution_m":1000,"lst_composite_start":"2026-04-01",'
        '"lst_composite_end":"2026-06-30"}',
        encoding="utf-8",
    )
    (directory / "ac_001_gummidipoondi_2026.csv").write_text(
        "constituency_id,season_year,lst_c,ndvi,ndbi,ndwi,"
        "lst_valid,ndvi_valid,ndbi_valid,ndwi_valid\n"
        "ac_001_gummidipoondi,2026,40,0.4,0.1,-0.2,True,True,True,True\n"
        "ac_001_gummidipoondi,2026,42,0.6,, -0.4,True,True,False,True\n",
        encoding="utf-8",
    )

    summary = load_satellite_summary(
        database_path,
        region_id=f"constituency_{constituency_id}",
        season_year=2026,
        cache_dir=tmp_path,
    )

    assert summary.data_status == "available"
    assert summary.grid_cell_count == 2
    assert summary.grid_resolution_m == 1000
    assert summary.lst.mean == pytest.approx(41)
    assert summary.ndvi.mean == pytest.approx(0.5)
    assert summary.ndbi.mean == pytest.approx(0.1)
    assert summary.ndbi.coverage_percent == 50
    assert summary.ndwi.mean == pytest.approx(-0.3)
    assert summary.composite_start == "2026-04-01"
    assert summary.composite_end == "2026-06-30"


def test_constituency_scatter_uses_only_valid_paired_cached_cells(tmp_path) -> None:
    directory = (
        tmp_path
        / "processed"
        / "constituencies"
        / "static_batches"
        / "ac_001_gummidipoondi"
    )
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        '{"constituency_id":"ac_001_gummidipoondi","season_year":2026,'
        '"input_resolution_m":1000,"lst_composite_start":"2026-04-01",'
        '"lst_composite_end":"2026-06-30"}',
        encoding="utf-8",
    )
    (directory / "ac_001_gummidipoondi_2026.csv").write_text(
        "ndvi,lst_c\n0.1,30\n0.5,40\n,41\n1.1,45\n",
        encoding="utf-8",
    )

    summary = load_constituency_scatter(
        tmp_path,
        constituency_id="ac_001_gummidipoondi",
        season_year=2026,
    )

    assert summary.data_status == "available"
    assert summary.resolution_m == 1000
    assert summary.pair_count == 2
    assert summary.correlation_pearson == pytest.approx(1.0)
    assert summary.composite_start == "2026-04-01"
    assert summary.points[0].ndvi == pytest.approx(0.1)


def test_constituency_scatter_reports_missing_cached_cells(tmp_path) -> None:
    summary = load_constituency_scatter(
        tmp_path,
        constituency_id="ac_001_gummidipoondi",
        season_year=2026,
    )

    assert summary.data_status == "unavailable"
    assert summary.pair_count == 0
    assert summary.correlation_pearson is None
    assert "No cached constituency grid" in summary.reason
