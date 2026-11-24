import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from app.schemas.weather import WeatherResponse


class GridPersistenceError(RuntimeError):
    """Raised when processed grid records cannot be persisted to SQLite."""


INSERT_GRID = """
INSERT OR REPLACE INTO grid_observations (
    grid_id, manifest_id, region_id, resolution_m, season_year,
    grid_row, grid_col, centroid_lon, centroid_lat,
    lst_c, lst_valid_scenes, ndvi, ndvi_valid_scenes,
    ndbi, ndbi_valid_scenes, ndwi, ndwi_valid_scenes,
    population_estimated_2025, population_age_2020,
    children_estimated_2020, elderly_estimated_2020,
    lst_valid, ndvi_valid, ndbi_valid, ndwi_valid, population_valid,
    children_share_2020, elderly_share_2020,
    data_status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def save_grid_observations(
    database_path: Path,
    records: pd.DataFrame,
    manifest: dict[str, Any],
) -> int:
    if records.empty:
        raise GridPersistenceError("Refusing to persist an empty grid dataset.")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    rows = (
        tuple(_sqlite_value(value) for value in row)
        for row in records[
            [
                "grid_id",
                "manifest_id",
                "region_id",
                "resolution_m",
                "season_year",
                "grid_row",
                "grid_col",
                "centroid_lon",
                "centroid_lat",
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
                "lst_valid",
                "ndvi_valid",
                "ndbi_valid",
                "ndwi_valid",
                "population_valid",
                "children_share_2020",
                "elderly_share_2020",
                "data_status",
            ]
        ].itertuples(index=False, name=None)
    )
    try:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_manifests (
                    manifest_id TEXT PRIMARY KEY,
                    region_id TEXT NOT NULL,
                    season_year INTEGER NOT NULL,
                    resolution_m INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS grid_observations (
                    grid_id TEXT NOT NULL,
                    manifest_id TEXT NOT NULL REFERENCES dataset_manifests(manifest_id),
                    region_id TEXT NOT NULL,
                    resolution_m INTEGER NOT NULL,
                    season_year INTEGER NOT NULL,
                    grid_row INTEGER NOT NULL,
                    grid_col INTEGER NOT NULL,
                    centroid_lon REAL NOT NULL,
                    centroid_lat REAL NOT NULL,
                    lst_c REAL,
                    lst_valid_scenes REAL,
                    ndvi REAL,
                    ndvi_valid_scenes REAL,
                    ndbi REAL,
                    ndbi_valid_scenes REAL,
                    ndwi REAL,
                    ndwi_valid_scenes REAL,
                    population_estimated_2025 REAL,
                    population_age_2020 REAL,
                    children_estimated_2020 REAL,
                    elderly_estimated_2020 REAL,
                    lst_valid INTEGER NOT NULL,
                    ndvi_valid INTEGER NOT NULL,
                    ndbi_valid INTEGER NOT NULL,
                    ndwi_valid INTEGER NOT NULL,
                    population_valid INTEGER NOT NULL,
                    children_share_2020 REAL,
                    elderly_share_2020 REAL,
                    data_status TEXT NOT NULL,
                    PRIMARY KEY (grid_id, season_year)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_grid_region_season
                ON grid_observations (region_id, season_year, resolution_m)
                """
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO dataset_manifests
                    (manifest_id, region_id, season_year, resolution_m, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    manifest["manifest_id"],
                    manifest["region_id"],
                    manifest["season_year"],
                    manifest["resolution_m"],
                    json.dumps(manifest, sort_keys=True, default=str),
                ),
            )
            connection.executemany(INSERT_GRID, rows)
            return len(records)
    except sqlite3.Error as exc:
        raise GridPersistenceError(
            f"Could not persist {len(records)} grid cells to {database_path}: {exc}"
        ) from exc


def _sqlite_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return int(value)
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def save_weather_observations(
    database_path: Path,
    weather: WeatherResponse,
) -> tuple[int, int]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    daily_rows = [
        (
            weather.location_id,
            day.isoformat(),
            weather.provenance.model,
            weather.provenance.requested_latitude,
            weather.provenance.requested_longitude,
            weather.latitude,
            weather.longitude,
            _sqlite_value(maximum),
            _sqlite_value(minimum),
            _sqlite_value(mean),
            _sqlite_value(wind),
            weather.provenance.data_status,
        )
        for day, maximum, minimum, mean, wind in zip(
            weather.daily.time,
            weather.daily.temperature_2m_max,
            weather.daily.temperature_2m_min,
            weather.daily.temperature_2m_mean,
            weather.daily.wind_speed_10m_max,
            strict=True,
        )
    ]
    hourly_rows = [
        (
            weather.location_id,
            timestamp.isoformat(),
            weather.provenance.model,
            weather.provenance.requested_latitude,
            weather.provenance.requested_longitude,
            weather.latitude,
            weather.longitude,
            _sqlite_value(temperature),
            _sqlite_value(humidity),
            _sqlite_value(wind),
            weather.provenance.data_status,
        )
        for timestamp, temperature, humidity, wind in zip(
            weather.hourly.time,
            weather.hourly.temperature_2m,
            weather.hourly.relative_humidity_2m,
            weather.hourly.wind_speed_10m,
            strict=True,
        )
    ]
    try:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS weather_daily (
                    location_id TEXT NOT NULL,
                    date_local TEXT NOT NULL,
                    model TEXT NOT NULL,
                    requested_latitude REAL NOT NULL,
                    requested_longitude REAL NOT NULL,
                    resolved_latitude REAL NOT NULL,
                    resolved_longitude REAL NOT NULL,
                    temperature_2m_max_c REAL,
                    temperature_2m_min_c REAL,
                    temperature_2m_mean_c REAL,
                    wind_speed_10m_max_kmh REAL,
                    data_status TEXT NOT NULL,
                    PRIMARY KEY (location_id, date_local, model)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS weather_hourly (
                    location_id TEXT NOT NULL,
                    timestamp_local TEXT NOT NULL,
                    model TEXT NOT NULL,
                    requested_latitude REAL NOT NULL,
                    requested_longitude REAL NOT NULL,
                    resolved_latitude REAL NOT NULL,
                    resolved_longitude REAL NOT NULL,
                    temperature_2m_c REAL,
                    relative_humidity_2m_percent REAL,
                    wind_speed_10m_kmh REAL,
                    data_status TEXT NOT NULL,
                    PRIMARY KEY (location_id, timestamp_local, model)
                )
                """
            )
            connection.executemany(
                """
                INSERT OR REPLACE INTO weather_daily VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                daily_rows,
            )
            connection.executemany(
                """
                INSERT OR REPLACE INTO weather_hourly VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                hourly_rows,
            )
    except sqlite3.Error as exc:
        raise GridPersistenceError(
            f"Could not persist Open-Meteo observations for "
            f"{weather.location_id}: {exc}"
        ) from exc
    return len(daily_rows), len(hourly_rows)


def save_district_summaries(
    database_path: Path,
    summaries: pd.DataFrame,
    *,
    boundary_manifest: dict[str, Any],
) -> int:
    if summaries.empty:
        raise GridPersistenceError("Refusing to persist an empty district summary.")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    rows = (
        tuple(_sqlite_value(value) for value in row)
        for row in summaries.itertuples(index=False, name=None)
    )
    try:
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS district_aggregates (
                    district_id TEXT NOT NULL,
                    district_name TEXT NOT NULL,
                    season_year INTEGER NOT NULL,
                    cell_count INTEGER NOT NULL,
                    lst_valid_cells INTEGER NOT NULL,
                    lst_coverage_pct REAL,
                    lst_mean_c REAL,
                    lst_max_c REAL,
                    ndvi_valid_cells INTEGER NOT NULL,
                    ndvi_mean REAL,
                    ndbi_mean REAL,
                    ndwi_mean REAL,
                    population_valid_cells INTEGER NOT NULL,
                    population_estimated_2025 REAL,
                    population_age_2020 REAL,
                    children_estimated_2020 REAL,
                    elderly_estimated_2020 REAL,
                    children_share_2020 REAL,
                    elderly_share_2020 REAL,
                    data_status TEXT NOT NULL,
                    boundary_manifest_json TEXT NOT NULL,
                    PRIMARY KEY (district_id, season_year)
                )
                """
            )
            placeholders = ",".join("?" for _ in range(len(summaries.columns) + 1))
            connection.executemany(
                f"INSERT OR REPLACE INTO district_aggregates VALUES ({placeholders})",
                (
                    (*row, json.dumps(boundary_manifest, sort_keys=True))
                    for row in rows
                ),
            )
    except sqlite3.Error as exc:
        raise GridPersistenceError(
            f"Could not persist district summaries: {exc}"
        ) from exc
    return len(summaries)
