import csv
import threading
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

WeatherSummary = tuple[
    float | None,
    float | None,
    str | None,
    str | None,
    str | None,
    str | None,
]


class _WeatherAccumulator(TypedDict):
    mean: list[float]
    maximum: list[float]
    models: list[str]
    statuses: list[str]
    dates: list[str]


_WEATHER_CACHE_LOCK = threading.RLock()
_EMPTY_SUMMARY: WeatherSummary = (None, None, None, None, None, None)


def load_cached_weather_summary(
    cache_dir: Path,
    *,
    location_id: str,
    season_year: int,
) -> WeatherSummary:
    daily_directory = cache_dir / "processed" / "open_meteo"
    if not daily_directory.is_dir():
        return _EMPTY_SUMMARY

    version: list[tuple[str, int, int, int]] = []
    for path in sorted(daily_directory.glob("*_daily.csv")):
        try:
            stat = path.stat()
            version.append(
                (str(path.resolve()), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
            )
        except OSError:
            version.append((str(path.resolve()), -1, -1, -1))

    with _WEATHER_CACHE_LOCK:
        summaries = _read_weather_summaries(
            season_year,
            tuple(version),
        )
        return summaries.get(location_id, _EMPTY_SUMMARY)


def clear_weather_summary_cache() -> None:
    with _WEATHER_CACHE_LOCK:
        _read_weather_summaries.cache_clear()


@lru_cache(maxsize=4)
def _read_weather_summaries(
    season_year: int,
    version: tuple[tuple[str, int, int, int], ...],
) -> dict[str, WeatherSummary]:
    start_date = f"{season_year}-04-01"
    end_date = f"{season_year}-06-30"
    accumulators: dict[str, _WeatherAccumulator] = {}

    for path_string, _, _, _ in version:
        try:
            with Path(path_string).open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    location_id = row.get("location_id")
                    row_date = row.get("date_local")
                    if (
                        not location_id
                        or not row_date
                        or row_date < start_date
                        or row_date > end_date
                    ):
                        continue
                    values = accumulators.setdefault(
                        location_id,
                        {
                            "mean": [],
                            "maximum": [],
                            "models": [],
                            "statuses": [],
                            "dates": [],
                        },
                    )
                    values["dates"].append(row_date)
                    if row.get("model"):
                        values["models"].append(row["model"])
                    if row.get("data_status"):
                        values["statuses"].append(row["data_status"])
                    try:
                        if row.get("temperature_2m_mean_c"):
                            values["mean"].append(float(row["temperature_2m_mean_c"]))
                        if row.get("temperature_2m_max_c"):
                            values["maximum"].append(float(row["temperature_2m_max_c"]))
                    except ValueError:
                        continue
        except (OSError, csv.Error):
            continue

    summaries: dict[str, WeatherSummary] = {}
    for location_id, values in accumulators.items():
        mean_values = values["mean"]
        maximum_values = values["maximum"]
        if not mean_values and not maximum_values:
            summaries[location_id] = _EMPTY_SUMMARY
            continue
        dates = values["dates"]
        models = values["models"]
        statuses = values["statuses"]
        summaries[location_id] = (
            sum(mean_values) / len(mean_values) if mean_values else None,
            max(maximum_values) if maximum_values else None,
            sorted(models)[0] if models else None,
            sorted(statuses)[0] if statuses else None,
            min(dates) if dates else None,
            max(dates) if dates else None,
        )
    return summaries
