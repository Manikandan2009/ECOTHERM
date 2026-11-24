import csv
import json
import math
import sqlite3
from pathlib import Path

from app.schemas.satellite import (
    SatelliteAnalysisSummary,
    SatelliteMetric,
    SatelliteScatterPoint,
    SatelliteScatterSummary,
)

METRICS = ("lst_c", "ndvi", "ndbi", "ndwi")


class SatelliteRepositoryError(RuntimeError):
    """Raised when cached satellite summary data cannot be read."""


def load_constituency_scatter(
    cache_dir: Path,
    *,
    constituency_id: str,
    season_year: int,
) -> SatelliteScatterSummary:
    directory = (
        cache_dir
        / "processed"
        / "constituencies"
        / "static_batches"
        / constituency_id
    )
    csv_path = directory / f"{constituency_id}_{season_year}.csv"
    manifest_path = directory / "manifest.json"
    if not csv_path.is_file() or not manifest_path.is_file():
        return _unavailable_scatter(
            constituency_id,
            season_year,
            "No cached constituency grid and provenance manifest are available.",
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise SatelliteRepositoryError(
                "Cached constituency manifest must contain an object."
            )
        with csv_path.open("r", encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            if not {"ndvi", "lst_c"}.issubset(reader.fieldnames or ()):
                raise SatelliteRepositoryError(
                    "Cached constituency grid is missing NDVI/LST columns."
                )
            points = []
            for row in reader:
                try:
                    ndvi = float(row["ndvi"])
                    lst_c = float(row["lst_c"])
                except (TypeError, ValueError):
                    continue
                if (
                    math.isfinite(ndvi)
                    and -1 <= ndvi <= 1
                    and math.isfinite(lst_c)
                    and 0 <= lst_c <= 80
                ):
                    points.append(SatelliteScatterPoint(ndvi=ndvi, lst_c=lst_c))
    except SatelliteRepositoryError:
        raise
    except (OSError, json.JSONDecodeError, csv.Error) as exc:
        raise SatelliteRepositoryError(
            f"Could not read cached constituency satellite cells: {exc}"
        ) from exc

    if (
        manifest.get("constituency_id") != constituency_id
        or manifest.get("season_year") != season_year
    ):
        return _unavailable_scatter(
            constituency_id,
            season_year,
            "Cached constituency manifest does not match the requested region and season.",
        )
    if not points:
        return _unavailable_scatter(
            constituency_id,
            season_year,
            "No cells contain both valid NDVI and LST values for the selected composite.",
            resolution_m=_manifest_resolution(manifest),
        )

    correlation = _pearson_correlation(
        [point.ndvi for point in points],
        [point.lst_c for point in points],
    )
    reason = (
        None
        if correlation is not None
        else "Correlation is unavailable because at least two varying paired cells are required."
    )
    return SatelliteScatterSummary(
        constituency_id=constituency_id,
        season_year=season_year,
        data_status="available",
        resolution_m=_manifest_resolution(manifest),
        pair_count=len(points),
        correlation_pearson=correlation,
        composite_start=manifest.get("lst_composite_start"),
        composite_end=manifest.get("lst_composite_end"),
        reason=reason,
        points=points,
    )


def _pearson_correlation(x_values: list[float], y_values: list[float]) -> float | None:
    if len(x_values) < 2:
        return None
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    x_centered = [value - x_mean for value in x_values]
    y_centered = [value - y_mean for value in y_values]
    denominator = math.sqrt(
        sum(value * value for value in x_centered)
        * sum(value * value for value in y_centered)
    )
    if denominator == 0:
        return None
    return sum(
        x * y for x, y in zip(x_centered, y_centered, strict=True)
    ) / denominator


def _manifest_resolution(manifest: dict) -> int | None:
    value = manifest.get("input_resolution_m")
    return int(value) if isinstance(value, int) and value > 0 else None


def _unavailable_scatter(
    constituency_id: str,
    season_year: int,
    reason: str,
    *,
    resolution_m: int | None = None,
) -> SatelliteScatterSummary:
    return SatelliteScatterSummary(
        constituency_id=constituency_id,
        season_year=season_year,
        data_status="unavailable",
        resolution_m=resolution_m,
        pair_count=0,
        correlation_pearson=None,
        composite_start=None,
        composite_end=None,
        reason=reason,
        points=[],
    )


def load_satellite_summary(
    database_path: Path,
    *,
    region_id: str,
    season_year: int,
    cache_dir: Path | None = None,
) -> SatelliteAnalysisSummary:
    row = None
    if database_path.is_file():
        try:
            database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
            with sqlite3.connect(database_uri, uri=True) as connection:
                table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='grid_observations'"
                ).fetchone()
                if table:
                    row = connection.execute(
                        """
                        SELECT
                            COUNT(*),
                            MIN(resolution_m),
                            COUNT(lst_c), AVG(lst_c),
                            COUNT(ndvi), AVG(ndvi),
                            COUNT(ndbi), AVG(ndbi),
                            COUNT(ndwi), AVG(ndwi)
                        FROM grid_observations
                        WHERE region_id = ? AND season_year = ?
                        """,
                        (region_id, season_year),
                    ).fetchone()
        except sqlite3.Error as exc:
            raise SatelliteRepositoryError(
                f"Could not read the cached satellite summary: {exc}"
            ) from exc

    if row is None or not row[0]:
        if cache_dir is not None and region_id.startswith("constituency_"):
            constituency_id = region_id.removeprefix("constituency_")
            return _load_constituency_batch_summary(
                cache_dir,
                constituency_id=constituency_id,
                season_year=season_year,
            )
        return _unavailable_summary(region_id, season_year)

    cell_count = int(row[0])
    metrics = [
        _metric(cell_count, row[offset], row[offset + 1])
        for offset in (2, 4, 6, 8)
    ]
    valid_metrics = sum(metric.valid_cell_count not in (None, 0) for metric in metrics)
    return SatelliteAnalysisSummary(
        region_id=region_id,
        season_year=season_year,
        data_status="available" if valid_metrics == len(METRICS) else "partial",
        grid_cell_count=cell_count,
        grid_resolution_m=int(row[1]) if row[1] is not None else None,
        lst=metrics[0],
        ndvi=metrics[1],
        ndbi=metrics[2],
        ndwi=metrics[3],
        composite_start=f"{season_year}-04-01",
        composite_end=f"{season_year}-06-30",
    )


def _load_constituency_batch_summary(
    cache_dir: Path,
    *,
    constituency_id: str,
    season_year: int,
) -> SatelliteAnalysisSummary:
    directory = (
        cache_dir
        / "processed"
        / "constituencies"
        / "static_batches"
        / constituency_id
    )
    csv_path = directory / f"{constituency_id}_{season_year}.csv"
    manifest_path = directory / "manifest.json"
    if not csv_path.is_file() or not manifest_path.is_file():
        return _unavailable_summary(f"constituency_{constituency_id}", season_year)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise SatelliteRepositoryError(
                "Cached constituency manifest must contain an object."
            )
        if (
            manifest.get("constituency_id") != constituency_id
            or manifest.get("season_year") != season_year
        ):
            return _unavailable_summary(f"constituency_{constituency_id}", season_year)
        with csv_path.open("r", encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            required_columns = {*METRICS, "constituency_id", "season_year"}
            if not required_columns.issubset(reader.fieldnames or ()):
                raise SatelliteRepositoryError(
                    "Cached constituency grid is missing satellite metric columns."
                )
            values = {metric: [] for metric in METRICS}
            cell_count = 0
            for row in reader:
                if (
                    row["constituency_id"] != constituency_id
                    or row["season_year"] != str(season_year)
                ):
                    raise SatelliteRepositoryError(
                        "Cached constituency grid contains a row for another region or season."
                    )
                cell_count += 1
                for metric in METRICS:
                    valid_column = f"{metric.split('_')[0]}_valid"
                    if (
                        row.get(valid_column) is not None
                        and row[valid_column].strip().lower() not in {"true", "1"}
                    ):
                        continue
                    try:
                        value = float(row[metric])
                    except (TypeError, ValueError):
                        continue
                    lower, upper = (0, 80) if metric == "lst_c" else (-1, 1)
                    if math.isfinite(value) and lower <= value <= upper:
                        values[metric].append(value)
    except SatelliteRepositoryError:
        raise
    except (OSError, json.JSONDecodeError, csv.Error) as exc:
        raise SatelliteRepositoryError(
            f"Could not read cached constituency satellite cells: {exc}"
        ) from exc

    if not cell_count:
        return _unavailable_summary(f"constituency_{constituency_id}", season_year)

    metrics = [
        _metric(
            cell_count,
            len(values[metric]),
            sum(values[metric]) / len(values[metric]) if values[metric] else None,
        )
        for metric in METRICS
    ]
    valid_metrics = sum(metric.valid_cell_count not in (None, 0) for metric in metrics)
    return SatelliteAnalysisSummary(
        region_id=f"constituency_{constituency_id}",
        season_year=season_year,
        data_status="available" if valid_metrics == len(METRICS) else "partial",
        grid_cell_count=cell_count,
        grid_resolution_m=_manifest_resolution(manifest),
        lst=metrics[0],
        ndvi=metrics[1],
        ndbi=metrics[2],
        ndwi=metrics[3],
        composite_start=manifest.get("lst_composite_start"),
        composite_end=manifest.get("lst_composite_end"),
    )


def _metric(cell_count: int, valid_count: int, mean: float | None) -> SatelliteMetric:
    count = int(valid_count)
    return SatelliteMetric(
        mean=float(mean) if mean is not None else None,
        valid_cell_count=count,
        coverage_percent=count / cell_count * 100 if cell_count else None,
    )


def _unavailable_summary(
    region_id: str,
    season_year: int,
) -> SatelliteAnalysisSummary:
    unavailable = SatelliteMetric(
        mean=None,
        valid_cell_count=None,
        coverage_percent=None,
    )
    return SatelliteAnalysisSummary(
        region_id=region_id,
        season_year=season_year,
        data_status="unavailable",
        grid_cell_count=None,
        grid_resolution_m=None,
        lst=unavailable,
        ndvi=unavailable,
        ndbi=unavailable,
        ndwi=unavailable,
        composite_start=None,
        composite_end=None,
    )
