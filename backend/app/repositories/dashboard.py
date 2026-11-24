import sqlite3
from datetime import date
from pathlib import Path
import csv
import json
import math
from typing import Any

import numpy as np
import pandas as pd

from app.schemas.dashboard import DashboardSummary


def load_dashboard_summary(
    database_path: Path,
    *,
    region_id: str,
    season_year: int,
    grid_resolution_m: int | None,
) -> DashboardSummary:
    if region_id.startswith("constituency_"):
        constituency_id = region_id.removeprefix("constituency_")
        return _load_constituency_summary(
            database_path,
            constituency_id=constituency_id,
            season_year=season_year,
        )
    if region_id.startswith("district_"):
        district_id = region_id.removeprefix("district_")
        return _load_district_summary(
            database_path,
            district_id=district_id,
            season_year=season_year,
        )
    osm_summary = (
        _read_cached_osm_summary(database_path.parent.parent)
        if region_id == "tamil_nadu"
        else {}
    )
    if not database_path.is_file():
        mean, maximum, model, status, start_date, end_date = _read_cached_weather(
            database_path,
            location_id=f"{region_id}_reference",
            season_year=season_year,
        )
        unavailable = [
            "The local analysis database does not exist yet.",
            "people_exposed_high_heat",
            "high_risk_cell_count",
            "urban_heat_island_intensity",
        ]
        if region_id == "tamil_nadu" and not osm_summary:
            unavailable.append("osm_features")
        return DashboardSummary(
            region_id=region_id,
            season_year=season_year,
            data_status="partial" if mean is not None else "unavailable",
            grid_resolution_m=grid_resolution_m,
            grid_cell_count=None,
            lst_valid_cell_count=None,
            lst_coverage_percent=None,
            lst_mean_c=None,
            lst_max_c=None,
            estimated_population_2025=None,
            population_valid_cell_count=None,
            population_coverage_percent=None,
            weather_mean_air_temperature_c=mean,
            weather_max_air_temperature_c=maximum,
            weather_model=model,
            weather_data_status=status,
            weather_start_date=start_date,
            weather_end_date=end_date,
            osm_feature_counts=osm_summary.get("feature_counts"),
            osm_feature_total=osm_summary.get("total_feature_count"),
            osm_processed_at_utc=osm_summary.get("processed_at_utc"),
            unavailable_metrics=unavailable,
        )

    unavailable: list[str] = [
        "people_exposed_high_heat",
        "high_risk_cell_count",
        "urban_heat_island_intensity",
    ]
    if region_id == "tamil_nadu" and not osm_summary:
        unavailable.append("osm_features")
    grid_cell_count = None
    lst_valid_count = None
    lst_mean = None
    lst_max = None
    population = None
    population_valid_count = None
    weather = None
    weather_start = None
    weather_end = None
    try:
        database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(database_uri, uri=True) as connection:
            grid_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='grid_observations'"
            ).fetchone()
            if grid_table:
                row = connection.execute(
                    """
                    SELECT
                        COUNT(*),
                        SUM(CASE WHEN lst_c IS NOT NULL THEN 1 ELSE 0 END),
                        AVG(lst_c),
                        MAX(lst_c),
                        SUM(CASE WHEN population_estimated_2025 IS NOT NULL THEN 1 ELSE 0 END),
                        SUM(population_estimated_2025),
                        MIN(resolution_m)
                    FROM grid_observations
                    WHERE region_id = ? AND season_year = ?
                    """,
                    (region_id, season_year),
                ).fetchone()
                if row and row[0]:
                    (
                        grid_cell_count,
                        lst_valid_count,
                        lst_mean,
                        lst_max,
                        population_valid_count,
                        population,
                        stored_resolution,
                    ) = row
                    grid_resolution_m = grid_resolution_m or stored_resolution

            weather_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='weather_daily'"
            ).fetchone()
            weather = None
            if weather_table:
                weather = connection.execute(
                    """
                    SELECT AVG(temperature_2m_mean_c), MAX(temperature_2m_max_c),
                           MIN(model), MIN(data_status)
                    FROM weather_daily
                    WHERE location_id = ? AND date_local BETWEEN ? AND ?
                    """,
                    (
                        f"{region_id}_reference",
                        f"{season_year}-04-01",
                        f"{season_year}-06-30",
                    ),
                ).fetchone()
                if weather:
                    weather_dates = connection.execute(
                        """
                        SELECT MIN(date_local), MAX(date_local)
                        FROM weather_daily
                        WHERE location_id = ?
                          AND date_local BETWEEN ? AND ?
                        """,
                        (
                            f"{region_id}_reference",
                            f"{season_year}-04-01",
                            f"{season_year}-06-30",
                        ),
                    ).fetchone()
                    if weather_dates:
                        weather_start, weather_end = weather_dates
    except sqlite3.Error as exc:
        raise DashboardRepositoryError(
            f"Could not read the cached dashboard database: {exc}"
        ) from exc

    weather_mean = weather[0] if weather and weather[0] is not None else None
    weather_max = weather[1] if weather and weather[1] is not None else None
    weather_model = weather[2] if weather and weather[2] is not None else None
    weather_status = weather[3] if weather and weather[3] is not None else None
    if weather_mean is None:
        (
            weather_mean,
            weather_max,
            weather_model,
            weather_status,
            weather_start,
            weather_end,
        ) = _read_cached_weather(
            database_path,
            location_id=f"{region_id}_reference",
            season_year=season_year,
        )
    people_exposed = None
    high_risk_cells = None
    uhi_intensity = None
    if region_id == "tamil_nadu":
        people_exposed, high_risk_cells = _read_cached_risk_summary(
            database_path.parent.parent,
            season_year,
        )
        if lst_mean is not None:
            uhi_intensity = 0.0
        if people_exposed is not None:
            unavailable.remove("people_exposed_high_heat")
        if high_risk_cells is not None:
            unavailable.remove("high_risk_cell_count")
        if uhi_intensity is not None:
            unavailable.remove("urban_heat_island_intensity")
    if grid_cell_count:
        status = "available"
    elif weather_mean is not None:
        status = "partial"
    else:
        status = "unavailable"
    return DashboardSummary(
        region_id=region_id,
        season_year=season_year,
        data_status=status,
        grid_resolution_m=grid_resolution_m,
        grid_cell_count=grid_cell_count,
        lst_valid_cell_count=lst_valid_count,
        lst_coverage_percent=(
            lst_valid_count / grid_cell_count * 100
            if grid_cell_count and lst_valid_count is not None
            else None
        ),
        lst_mean_c=lst_mean,
        lst_max_c=lst_max,
        estimated_population_2025=population,
        population_valid_cell_count=population_valid_count,
        population_coverage_percent=(
            population_valid_count / grid_cell_count * 100
            if grid_cell_count and population_valid_count is not None
            else None
        ),
        weather_mean_air_temperature_c=weather_mean,
        weather_max_air_temperature_c=weather_max,
        weather_model=weather_model,
        weather_data_status=weather_status,
        weather_start_date=weather_start,
        weather_end_date=weather_end,
        people_exposed_high_heat=people_exposed,
        high_risk_cell_count=high_risk_cells,
        urban_heat_island_intensity_c=uhi_intensity,
        osm_feature_counts=osm_summary.get("feature_counts"),
        osm_feature_total=osm_summary.get("total_feature_count"),
        osm_processed_at_utc=osm_summary.get("processed_at_utc"),
        unavailable_metrics=unavailable,
    )


class DashboardRepositoryError(RuntimeError):
    """Raised when persisted dashboard summaries cannot be read."""


def _read_cached_osm_summary(cache_dir: Path) -> dict[str, Any]:
    path = cache_dir / "processed" / "openstreetmap" / "tamil_nadu_summary.json"
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise DashboardRepositoryError(
            f"Could not read the cached OpenStreetMap summary: {exc}"
        ) from exc
    counts = summary.get("feature_counts")
    total = summary.get("total_feature_count")
    if (
        not isinstance(counts, dict)
        or any(type(value) is not int or value < 0 for value in counts.values())
        or type(total) is not int
        or total < 0
    ):
        raise DashboardRepositoryError(
            "The cached OpenStreetMap summary has invalid feature counts."
        )
    return summary


def _read_cached_risk_summary(
    cache_dir: Path,
    season_year: int,
) -> tuple[float | None, int | None]:
    path = (
        cache_dir
        / "processed"
        / "grids"
        / f"tamil_nadu_1000m_{season_year}.csv"
    )
    if not path.is_file():
        return None, None
    try:
        cells = pd.read_csv(
            path,
            usecols=(
                "lst_c",
                "ndvi",
                "ndbi",
                "population_estimated_2025",
            ),
        )
    except (
        OSError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        ValueError,
    ) as exc:
        raise DashboardRepositoryError(
            f"Could not read the cached statewide risk inputs: {exc}"
        ) from exc
    return _calculate_heat_risk(cells)


def _calculate_heat_risk(
    cells: pd.DataFrame,
) -> tuple[float | None, int | None]:
    required = (
        "lst_c",
        "ndvi",
        "ndbi",
        "population_estimated_2025",
    )
    valid = cells.loc[:, required].replace([np.inf, -np.inf], np.nan).dropna()
    if valid.empty:
        return None, None
    exposure = valid["lst_c"].rank(pct=True).mul(100).clip(0, 100)
    low_vegetation = (
        ((0.4 - valid["ndvi"]).clip(-0.6, 0.6) + 0.6)
        .div(1.2)
        .mul(100)
        .clip(0, 100)
    )
    built_up = valid["ndbi"].clip(-1, 1).add(1).div(2).mul(100)
    population = valid["population_estimated_2025"]
    density_cap = population.quantile(0.95)
    density_score = (
        population.div(density_cap).mul(100).clip(0, 100)
        if pd.notna(density_cap) and density_cap > 0
        else pd.Series(0, index=valid.index)
    )
    vulnerability = (
        low_vegetation.mul(0.4)
        + built_up.mul(0.35)
        + density_score.mul(0.25)
    ).clip(0, 100)
    risk = exposure.mul(vulnerability).div(100).clip(0, 100)
    high_risk = risk >= 75
    people_exposed = float(population.loc[high_risk].sum())
    return people_exposed, int(high_risk.sum())


def _read_statewide_mean_lst(cache_dir: Path, season_year: int) -> float | None:
    state_csv = (
        cache_dir
        / "processed"
        / "grids"
        / f"tamil_nadu_1000m_{season_year}.csv"
    )
    if not state_csv.is_file():
        return None
    try:
        values = pd.read_csv(state_csv, usecols=["lst_c"])["lst_c"]
    except (
        OSError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        KeyError,
        ValueError,
    ):
        return None
    valid_values = values.replace([np.inf, -np.inf], np.nan).dropna()
    if valid_values.empty:
        return None
    mean = float(valid_values.mean())
    return mean if math.isfinite(mean) else None


def _coverage_percent(valid_cells: int | None, total_cells: int | None) -> float | None:
    if (
        total_cells is None
        or total_cells <= 0
        or valid_cells is None
        or valid_cells < 0
        or valid_cells > total_cells
    ):
        return None
    return valid_cells / total_cells * 100


def _load_constituency_summary(
    database_path: Path,
    *,
    constituency_id: str,
    season_year: int,
) -> DashboardSummary:
    cache_dir = database_path.parent.parent
    manifest_path = (
        cache_dir
        / "processed"
        / "constituencies"
        / "static_batches"
        / constituency_id
        / "manifest.json"
    )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        manifest = None
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardRepositoryError(
            f"Could not read the cached constituency summary: {exc}"
        ) from exc

    def numeric(key: str) -> float | None:
        value = manifest.get(key) if manifest else None
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    def count(key: str) -> int | None:
        value = numeric(key)
        return int(value) if value is not None else None

    def coverage_percent(coverage_key: str, valid_count_key: str) -> float | None:
        recorded_coverage = numeric(coverage_key)
        if recorded_coverage is not None:
            return (
                recorded_coverage
                if 0 <= recorded_coverage <= 100
                else None
            )
        return _coverage_percent(
            count(valid_count_key),
            count("grid_cell_count"),
        )

    risk_calculated = (
        manifest is not None
        and numeric("risk_score_mean") is not None
        and numeric("risk_score_max") is not None
    )
    people_exposed = numeric("people_exposed_high_heat") if risk_calculated else None
    high_risk_cells = count("high_risk_cell_count") if risk_calculated else None
    constituency_lst_mean = numeric("lst_mean_c")
    statewide_lst_mean = _read_statewide_mean_lst(cache_dir, season_year)
    uhi_intensity = (
        constituency_lst_mean - statewide_lst_mean
        if constituency_lst_mean is not None and statewide_lst_mean is not None
        else None
    )

    unavailable: list[str] = []
    if manifest is None:
        unavailable.extend(
            (
                "constituency_static_cache",
                "people_exposed_high_heat",
                "high_risk_cell_count",
            )
        )
    else:
        for key in (
            "lst_mean_c",
            "estimated_population_2025",
        ):
            if numeric(key) is None:
                unavailable.append(key)
        if people_exposed is None:
            unavailable.append("people_exposed_high_heat")
        if high_risk_cells is None:
            unavailable.append("high_risk_cell_count")
    if uhi_intensity is None:
        unavailable.append("urban_heat_island_intensity")

    return DashboardSummary(
        region_id=f"constituency_{constituency_id}",
        season_year=season_year,
        data_status="available" if manifest is not None else "unavailable",
        grid_resolution_m=1000,
        grid_cell_count=count("grid_cell_count"),
        lst_valid_cell_count=count("lst_valid_cell_count"),
        lst_coverage_percent=coverage_percent(
            "lst_coverage_percent", "lst_valid_cell_count"
        ),
        lst_mean_c=numeric("lst_mean_c"),
        lst_max_c=numeric("lst_max_c"),
        estimated_population_2025=numeric("population_estimated_2025"),
        population_valid_cell_count=count("population_valid_cell_count"),
        population_coverage_percent=coverage_percent(
            "population_coverage_percent", "population_valid_cell_count"
        ),
        weather_mean_air_temperature_c=None,
        weather_max_air_temperature_c=None,
        weather_model=None,
        weather_data_status=None,
        weather_start_date=None,
        weather_end_date=None,
        urban_heat_island_intensity_c=uhi_intensity,
        people_exposed_high_heat=people_exposed,
        high_risk_cell_count=high_risk_cells,
        unavailable_metrics=unavailable,
    )


def _load_district_summary(
    database_path: Path,
    *,
    district_id: str,
    season_year: int,
) -> DashboardSummary:
    cache_dir = database_path.parent.parent
    manifest_path = (
        cache_dir
        / "processed"
        / "districts"
        / "static_batches"
        / district_id
        / "manifest.json"
    )
    manifest: dict[str, object] | None = None
    if manifest_path.is_file():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                manifest = payload
        except (OSError, json.JSONDecodeError):
            manifest = None

    lst_mean = manifest.get("lst_mean_c") if manifest else None
    lst_max = manifest.get("lst_max_c") if manifest else None
    lst_valid = manifest.get("lst_valid_cells") if manifest else None
    cell_count = manifest.get("cell_count") if manifest else None
    population = manifest.get("worldpop_population_2025") if manifest else None
    population_valid = manifest.get("population_valid_cells") if manifest else None
    district_name = str(manifest.get("district_name", district_id)) if manifest else district_id

    people_exposed: float | None = None
    high_risk_cells: int | None = None
    uhi_intensity: float | None = None
    csv_path = (
        cache_dir
        / "processed"
        / "districts"
        / "static_batches"
        / district_id
        / f"{district_id}_{season_year}.csv"
    )
    if csv_path.is_file():
        try:
            district_cells = pd.read_csv(csv_path)
            people_exposed, high_risk_cells = _calculate_heat_risk(district_cells)
        except (OSError, pd.errors.EmptyDataError, KeyError, ValueError):
            people_exposed = None
            high_risk_cells = None
    state_mean = _read_statewide_mean_lst(cache_dir, season_year)
    if state_mean is not None and lst_mean is not None:
        uhi_intensity = float(lst_mean) - state_mean

    weather_location = f"{district_id}_reference"
    weather = _read_cached_weather(
        database_path,
        location_id=weather_location,
        season_year=season_year,
    )
    weather_mean, weather_max, weather_model, weather_status, weather_start, weather_end = weather

    unavailable = []
    if people_exposed is None:
        unavailable.append("people_exposed_high_heat")
    if high_risk_cells is None:
        unavailable.append("high_risk_cell_count")
    if uhi_intensity is None:
        unavailable.append("urban_heat_island_intensity")
    if manifest is None:
        unavailable.append("district_static_cache")

    return DashboardSummary(
        region_id=f"district_{district_id}",
        season_year=season_year,
        data_status="available" if manifest is not None or weather_mean is not None else "unavailable",
        grid_resolution_m=1000,
        grid_cell_count=int(cell_count) if cell_count is not None else None,
        lst_valid_cell_count=int(lst_valid) if lst_valid is not None else None,
        lst_coverage_percent=_coverage_percent(
            int(lst_valid) if lst_valid is not None else None,
            int(cell_count) if cell_count is not None else None,
        ),
        lst_mean_c=float(lst_mean) if lst_mean is not None else None,
        lst_max_c=float(lst_max) if lst_max is not None else None,
        estimated_population_2025=float(population) if population is not None else None,
        population_valid_cell_count=int(population_valid) if population_valid is not None else None,
        population_coverage_percent=_coverage_percent(
            int(population_valid) if population_valid is not None else None,
            int(cell_count) if cell_count is not None else None,
        ),
        weather_mean_air_temperature_c=weather_mean,
        weather_max_air_temperature_c=weather_max,
        weather_model=weather_model,
        weather_data_status=weather_status,
        weather_start_date=weather_start,
        weather_end_date=weather_end,
        urban_heat_island_intensity_c=uhi_intensity,
        people_exposed_high_heat=people_exposed,
        high_risk_cell_count=high_risk_cells,
        unavailable_metrics=unavailable,
    )


def _read_cached_weather(
    database_path: Path,
    *,
    location_id: str,
    season_year: int,
) -> tuple[float | None, float | None, str | None, str | None,
           str | None, str | None]:
    cache_dir = database_path.parent.parent
    daily_directory = cache_dir / "processed" / "open_meteo"
    if not daily_directory.is_dir():
        return None, None, None, None, None, None

    start_date = f"{season_year}-04-01"
    end_date = f"{season_year}-06-30"
    mean_values: list[float] = []
    max_values: list[float] = []
    models: set[str] = set()
    statuses: set[str] = set()
    dates: list[str] = []

    for csv_path in sorted(daily_directory.glob("*_daily.csv")):
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    if row.get("location_id") != location_id:
                        continue
                    row_date = row.get("date_local")
                    if not row_date or row_date < start_date or row_date > end_date:
                        continue
                    dates.append(row_date)
                    if row.get("model"):
                        models.add(row["model"])
                    if row.get("data_status"):
                        statuses.add(row["data_status"])
                    try:
                        if row.get("temperature_2m_mean_c"):
                            mean_values.append(float(row["temperature_2m_mean_c"]))
                        if row.get("temperature_2m_max_c"):
                            max_values.append(float(row["temperature_2m_max_c"]))
                    except ValueError:
                        continue
        except (OSError, csv.Error):
            continue

    if not mean_values and not max_values:
        return None, None, None, None, None, None
    return (
        sum(mean_values) / len(mean_values) if mean_values else None,
        max(max_values) if max_values else None,
        sorted(models)[0] if models else None,
        sorted(statuses)[0] if statuses else None,
        min(dates) if dates else None,
        max(dates) if dates else None,
    )


def _unavailable_summary(
    region_id: str,
    season_year: int,
    grid_resolution_m: int | None,
    reason: str,
) -> DashboardSummary:
    return DashboardSummary(
        region_id=region_id,
        season_year=season_year,
        data_status="unavailable",
        grid_resolution_m=grid_resolution_m,
        grid_cell_count=None,
        lst_valid_cell_count=None,
        lst_coverage_percent=None,
        lst_mean_c=None,
        lst_max_c=None,
        estimated_population_2025=None,
        population_valid_cell_count=None,
        population_coverage_percent=None,
        weather_mean_air_temperature_c=None,
        weather_max_air_temperature_c=None,
        weather_model=None,
        weather_data_status=None,
        unavailable_metrics=[
            reason,
            "people_exposed_high_heat",
            "high_risk_cell_count",
            "urban_heat_island_intensity",
        ],
    )
