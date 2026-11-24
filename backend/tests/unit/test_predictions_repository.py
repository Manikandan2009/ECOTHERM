import sqlite3

from app.repositories.predictions import load_prediction_status


def _create_grid_database(database_path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE grid_observations (
                region_id TEXT,
                season_year INTEGER,
                lst_c REAL
            )
            """
        )


def test_prediction_status_reports_one_season_and_no_qualified_model(tmp_path) -> None:
    database_path = tmp_path / "ecotherm.sqlite"
    _create_grid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            "INSERT INTO grid_observations VALUES (?, ?, ?)",
            [
                ("tamil_nadu", 2026, 40.0),
                ("tamil_nadu", 2026, None),
                ("chennai", 2026, 38.0),
            ],
        )

    status = load_prediction_status(
        database_path,
        region_id="tamil_nadu",
    )

    assert status.status == "unavailable"
    assert status.prediction_available is False
    assert status.available_season_years == [2026]
    assert status.region_season_years == [2026]
    assert status.latest_region_cell_count == 2
    assert status.latest_region_lst_valid_cell_count == 1
    assert status.target_status == "not_defined"
    assert status.baseline_status == "not_evaluated"
    assert status.spatial_validation_status == "not_run"
    assert status.temporal_validation_status == "not_run"
    assert "separate season" in status.reason


def test_prediction_status_does_not_claim_model_when_more_seasons_exist(tmp_path) -> None:
    database_path = tmp_path / "ecotherm.sqlite"
    _create_grid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            "INSERT INTO grid_observations VALUES (?, ?, ?)",
            [
                ("tamil_nadu", 2025, 39.0),
                ("tamil_nadu", 2026, 40.0),
            ],
        )

    status = load_prediction_status(
        database_path,
        region_id="tamil_nadu",
    )

    assert status.available_season_years == [2025, 2026]
    assert status.prediction_available is False
    assert status.model_status == "no_qualified_model"
    assert "no qualified model" in status.reason


def test_prediction_status_returns_explicit_unavailability_without_cache(tmp_path) -> None:
    status = load_prediction_status(
        tmp_path / "missing.sqlite",
        region_id="tamil_nadu",
    )

    assert status.prediction_available is False
    assert status.available_season_years == []
    assert status.latest_region_cell_count is None
    assert "No cached analysis seasons" in status.reason
