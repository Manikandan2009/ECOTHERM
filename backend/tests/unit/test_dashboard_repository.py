import json
import sqlite3
import csv

import pandas as pd
import pytest

from app.repositories.dashboard import load_dashboard_summary


def test_dashboard_summary_returns_only_persisted_weather_and_grid_data(
    tmp_path,
) -> None:
    database_path = tmp_path / "ecotherm.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE grid_observations (
                region_id TEXT,
                season_year INTEGER,
                resolution_m INTEGER,
                lst_c REAL,
                population_estimated_2025 REAL
            )
            """
        )
        connection.executemany(
            "INSERT INTO grid_observations VALUES (?, ?, ?, ?, ?)",
            [
                ("chennai", 2026, 100, 34.0, 100.0),
                ("chennai", 2026, 100, 38.0, None),
                ("chennai", 2026, 100, None, 50.0),
            ],
        )
        connection.execute(
            """
            CREATE TABLE weather_daily (
                location_id TEXT,
                date_local TEXT,
                temperature_2m_mean_c REAL,
                temperature_2m_max_c REAL,
                model TEXT,
                data_status TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO weather_daily VALUES (?, ?, ?, ?, ?, ?)",
            (
                "chennai_reference",
                "2026-04-01",
                30.0,
                36.0,
                "era5_land",
                "reanalysis_estimate",
            ),
        )

    summary = load_dashboard_summary(
        database_path,
        region_id="chennai",
        season_year=2026,
        grid_resolution_m=100,
    )

    assert summary.data_status == "available"
    assert summary.grid_cell_count == 3
    assert summary.lst_valid_cell_count == 2
    assert summary.lst_mean_c == 36.0
    assert summary.estimated_population_2025 == 150.0
    assert summary.population_coverage_percent == pytest.approx(200 / 3)
    assert summary.weather_mean_air_temperature_c == 30.0
    assert summary.weather_data_status == "reanalysis_estimate"
    assert summary.people_exposed_high_heat is None


def test_dashboard_summary_marks_missing_sources_without_fabricating(
    tmp_path,
) -> None:
    database_path = tmp_path / "ecotherm.sqlite"
    summary = load_dashboard_summary(
        database_path,
        region_id="tamil_nadu",
        season_year=2026,
        grid_resolution_m=1000,
    )

    assert summary.data_status == "unavailable"
    assert summary.lst_mean_c is None
    assert summary.estimated_population_2025 is None
    assert summary.people_exposed_high_heat is None
    assert "people_exposed_high_heat" in summary.unavailable_metrics


def test_dashboard_summary_reads_grid_csv_without_sqlite(tmp_path) -> None:
    grid_directory = tmp_path / "processed" / "grids"
    grid_directory.mkdir(parents=True)
    pd.DataFrame(
        {
            "region_id": ["tamil_nadu", "tamil_nadu", "tamil_nadu"],
            "season_year": [2026, 2026, 2026],
            "resolution_m": [1000, 1000, 1000],
            "lst_c": [40.0, 42.0, None],
            "population_estimated_2025": [100.0, None, 300.0],
        }
    ).to_csv(grid_directory / "tamil_nadu_1000m_2026.csv", index=False)

    summary = load_dashboard_summary(
        tmp_path / "processed" / "ecotherm.sqlite",
        region_id="tamil_nadu",
        season_year=2026,
        grid_resolution_m=1000,
    )

    assert summary.data_status == "available"
    assert summary.grid_cell_count == 3
    assert summary.lst_valid_cell_count == 2
    assert summary.lst_mean_c == 41.0
    assert summary.estimated_population_2025 == 400.0
    assert summary.population_valid_cell_count == 2


def test_static_summaries_derive_coverage_from_cached_cell_counts(tmp_path) -> None:
    database_path = tmp_path / "processed" / "ecotherm.sqlite"
    cases = (
        (
            "district_mayiladuthurai",
            (
                "processed",
                "districts",
                "static_batches",
                "mayiladuthurai",
                "manifest.json",
            ),
            {
                "cell_count": 10,
                "lst_valid_cells": 8,
                "population_valid_cells": 5,
                "lst_mean_c": 40.0,
                "worldpop_population_2025": 500.0,
            },
        ),
        (
            "constituency_ac_021_anna_nagar",
            (
                "processed",
                "constituencies",
                "static_batches",
                "ac_021_anna_nagar",
                "manifest.json",
            ),
            {
                "grid_cell_count": 10,
                "lst_valid_cell_count": 8,
                "population_valid_cell_count": 5,
                "lst_mean_c": 40.0,
                "population_estimated_2025": 500.0,
            },
        ),
    )
    for region_id, manifest_parts, manifest in cases:
        manifest_path = tmp_path.joinpath(*manifest_parts)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        summary = load_dashboard_summary(
            database_path,
            region_id=region_id,
            season_year=2026,
            grid_resolution_m=1000,
        )

        assert summary.lst_coverage_percent == 80.0
        assert summary.population_coverage_percent == 50.0


def test_dashboard_summary_exposes_cached_tamil_nadu_osm_feature_counts(
    tmp_path,
) -> None:
    summary_path = (
        tmp_path
        / "processed"
        / "openstreetmap"
        / "tamil_nadu_summary.json"
    )
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(
        json.dumps(
            {
                "feature_counts": {
                    "buildings": 120,
                    "roads": 80,
                    "hospitals": 3,
                    "parks": 5,
                    "water_features": 10,
                    "bus_stops": 7,
                    "markets": 2,
                },
                "total_feature_count": 220,
                "processed_at_utc": "2026-11-24T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    summary = load_dashboard_summary(
        tmp_path / "processed" / "ecotherm.sqlite",
        region_id="tamil_nadu",
        season_year=2026,
        grid_resolution_m=1000,
    )

    assert summary.osm_feature_total == 220
    assert summary.osm_feature_counts == {
        "buildings": 120,
        "roads": 80,
        "hospitals": 3,
        "parks": 5,
        "water_features": 10,
        "bus_stops": 7,
        "markets": 2,
    }
    assert summary.osm_processed_at_utc == "2026-11-24T10:00:00+00:00"


def test_tamil_nadu_summary_derives_cached_rule_based_risk_values(tmp_path) -> None:
    database_path = tmp_path / "processed" / "ecotherm.sqlite"
    database_path.parent.mkdir(parents=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE grid_observations (
                region_id TEXT,
                season_year INTEGER,
                resolution_m INTEGER,
                lst_c REAL,
                population_estimated_2025 REAL
            )
            """
        )
        connection.executemany(
            "INSERT INTO grid_observations VALUES (?, ?, ?, ?, ?)",
            [
                ("tamil_nadu", 2026, 1000, 30.0, 100.0),
                ("tamil_nadu", 2026, 1000, 35.0, 200.0),
                ("tamil_nadu", 2026, 1000, 40.0, 300.0),
                ("tamil_nadu", 2026, 1000, 45.0, 400.0),
            ],
        )
    grid_directory = tmp_path / "processed" / "grids"
    grid_directory.mkdir()
    pd.DataFrame(
        {
            "lst_c": [30.0, 35.0, 40.0, 45.0],
            "ndvi": [0.8, 0.2, -0.2, -0.5],
            "ndbi": [-0.5, 0.0, 0.7, 0.9],
            "population_estimated_2025": [100.0, 200.0, 300.0, 400.0],
        }
    ).to_csv(
        grid_directory / "tamil_nadu_1000m_2026.csv",
        index=False,
    )

    summary = load_dashboard_summary(
        database_path,
        region_id="tamil_nadu",
        season_year=2026,
        grid_resolution_m=1000,
    )

    assert summary.people_exposed_high_heat == 400.0
    assert summary.high_risk_cell_count == 1
    assert summary.urban_heat_island_intensity_c == 0.0
    assert "people_exposed_high_heat" not in summary.unavailable_metrics
    assert "high_risk_cell_count" not in summary.unavailable_metrics
    assert "urban_heat_island_intensity" not in summary.unavailable_metrics


def test_dashboard_summary_reads_existing_city_weather_cache(tmp_path) -> None:
    database_path = tmp_path / "processed" / "ecotherm.sqlite"
    database_path.parent.mkdir(parents=True)
    cache_directory = tmp_path / "processed" / "open_meteo"
    cache_directory.mkdir(parents=True)
    with (cache_directory / "chennai_daily.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "date_local",
                "location_id",
                "model",
                "data_status",
                "temperature_2m_max_c",
                "temperature_2m_mean_c",
            ]
        )
        writer.writerow(
            ["2026-04-01", "chennai_reference", "era5_land",
             "reanalysis_estimate", "36.0", "30.0"]
        )
        writer.writerow(
            ["2026-04-02", "chennai_reference", "era5_land",
             "reanalysis_estimate", "38.0", "32.0"]
        )

    summary = load_dashboard_summary(
        database_path,
        region_id="chennai",
        season_year=2026,
        grid_resolution_m=100,
    )

    assert summary.weather_mean_air_temperature_c == pytest.approx(31.0)
    assert summary.weather_max_air_temperature_c == 38.0
    assert summary.weather_model == "era5_land"
    assert summary.weather_start_date == "2026-04-01"
    assert summary.weather_end_date == "2026-04-02"


def test_constituency_summary_treats_non_finite_metrics_as_unavailable(tmp_path) -> None:
    database_path = tmp_path / "processed" / "ecotherm.sqlite"
    manifest_path = (
        tmp_path
        / "processed"
        / "constituencies"
        / "static_batches"
        / "ac_021_anna_nagar"
        / "manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "grid_cell_count": 1,
                "lst_valid_cell_count": 1,
                "lst_coverage_percent": 100.0,
                "lst_mean_c": 40.0,
                "lst_max_c": 40.0,
                "population_valid_cell_count": 1,
                "population_coverage_percent": 100.0,
                "population_estimated_2025": 100.0,
                "people_exposed_high_heat": float("nan"),
                "high_risk_cell_count": 0,
            }
        ),
        encoding="utf-8",
    )

    summary = load_dashboard_summary(
        database_path,
        region_id="constituency_ac_021_anna_nagar",
        season_year=2026,
        grid_resolution_m=1000,
    )

    assert summary.people_exposed_high_heat is None
    assert "people_exposed_high_heat" in summary.unavailable_metrics
    assert summary.high_risk_cell_count is None
    assert "high_risk_cell_count" in summary.unavailable_metrics


def test_constituency_summary_derives_heat_island_intensity_from_cached_grid(
    tmp_path,
) -> None:
    database_path = tmp_path / "processed" / "ecotherm.sqlite"
    grid_dir = tmp_path / "processed" / "grids"
    grid_dir.mkdir(parents=True)
    pd.DataFrame({"lst_c": [40.0, 42.0, None, float("inf")]}).to_csv(
        grid_dir / "tamil_nadu_1000m_2026.csv",
        index=False,
    )
    manifest_path = (
        tmp_path
        / "processed"
        / "constituencies"
        / "static_batches"
        / "ac_153_neyveli"
        / "manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"lst_mean_c": 40.5}),
        encoding="utf-8",
    )

    summary = load_dashboard_summary(
        database_path,
        region_id="constituency_ac_153_neyveli",
        season_year=2026,
        grid_resolution_m=1000,
    )

    assert summary.urban_heat_island_intensity_c == pytest.approx(-0.5)
    assert "urban_heat_island_intensity" not in summary.unavailable_metrics


def test_district_risk_counts_require_complete_risk_inputs(tmp_path) -> None:
    database_path = tmp_path / "processed" / "ecotherm.sqlite"
    district_dir = (
        tmp_path
        / "processed"
        / "districts"
        / "static_batches"
        / "test_district"
    )
    district_dir.mkdir(parents=True)
    manifest_path = district_dir / "manifest.json"
    csv_path = district_dir / "test_district_2026.csv"
    manifest_path.write_text(
        json.dumps(
            {
                "district_name": "Test District",
                "cell_count": 1,
                "lst_valid_cells": 0,
                "lst_mean_c": None,
                "lst_max_c": None,
                "worldpop_population_2025": None,
                "population_valid_cells": 0,
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "lst_c": None,
                "ndvi": 0.8,
                "ndbi": -1.0,
                "population_estimated_2025": None,
            }
        ]
    ).to_csv(csv_path, index=False)

    unavailable = load_dashboard_summary(
        database_path,
        region_id="district_test_district",
        season_year=2026,
        grid_resolution_m=1000,
    )
    assert unavailable.high_risk_cell_count is None
    assert unavailable.people_exposed_high_heat is None
    assert "high_risk_cell_count" in unavailable.unavailable_metrics

    manifest_path.write_text(
        json.dumps(
            {
                "district_name": "Test District",
                "cell_count": 1,
                "lst_valid_cells": 1,
                "lst_mean_c": 36.0,
                "lst_max_c": 36.0,
                "worldpop_population_2025": 10.0,
                "population_valid_cells": 1,
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "lst_c": 36.0,
                "ndvi": 1.0,
                "ndbi": -1.0,
                "population_estimated_2025": 10.0,
            }
        ]
    ).to_csv(csv_path, index=False)

    calculated_zero = load_dashboard_summary(
        database_path,
        region_id="district_test_district",
        season_year=2026,
        grid_resolution_m=1000,
    )
    assert calculated_zero.high_risk_cell_count == 0
    assert calculated_zero.people_exposed_high_heat == 0.0
    assert "high_risk_cell_count" not in calculated_zero.unavailable_metrics
