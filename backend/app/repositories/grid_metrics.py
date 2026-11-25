import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.repositories.grid_exports import GridExportError

_GRID_COLUMNS = (
    "lst_c",
    "ndvi",
    "ndbi",
    "ndwi",
    "population_estimated_2025",
)
_RISK_COLUMNS = (
    "lst_c",
    "ndvi",
    "ndbi",
    "population_estimated_2025",
)
_CACHE_SIZE = 8
_CACHE_LOCK = threading.RLock()


@dataclass(frozen=True)
class MetricSummary:
    valid_cell_count: int
    mean: float | None
    maximum: float | None


@dataclass(frozen=True)
class GridExportMetrics:
    columns: frozenset[str]
    grid_cell_count: int
    lst: MetricSummary | None
    lst_finite_mean: float | None
    ndvi: MetricSummary | None
    ndbi: MetricSummary | None
    ndwi: MetricSummary | None
    population_valid_cell_count: int | None
    estimated_population_2025: float | None
    people_exposed_high_heat: float | None
    high_risk_cell_count: int | None


@dataclass(frozen=True)
class RegionCsvMetrics:
    columns: frozenset[str]
    ndvi_mean: float | None
    heat_risk_calculated: bool
    people_exposed_high_heat: float | None
    high_risk_cell_count: int | None


_metrics_cache: OrderedDict[
    tuple[str, int, int, int, str, int, int],
    GridExportMetrics,
] = OrderedDict()
_REGION_CACHE_SIZE = 320
_region_metrics_cache: OrderedDict[
    tuple[str, int, int, int],
    RegionCsvMetrics,
] = OrderedDict()


def read_grid_export_metrics(
    cache_dir: Path,
    *,
    region_id: str,
    season_year: int,
    resolution_m: int,
    columns: tuple[str, ...],
    required_columns: tuple[str, ...],
) -> GridExportMetrics | None:
    path = (
        cache_dir
        / "processed"
        / "grids"
        / f"{region_id}_{resolution_m}m_{season_year}.csv"
    )
    if not path.is_file():
        return None

    requested_columns = set(columns) | set(required_columns)
    if not requested_columns.issubset(_GRID_COLUMNS):
        raise GridExportError("Requested cached grid metrics contain unsupported columns.")

    try:
        stat = path.stat()
        resolved_path = str(path.resolve())
    except OSError as exc:
        raise GridExportError(
            f"Could not inspect cached grid export {path.name}: {exc}"
        ) from exc

    key = (
        resolved_path,
        stat.st_mtime_ns,
        stat.st_ctime_ns,
        stat.st_size,
        region_id,
        season_year,
        resolution_m,
    )
    with _CACHE_LOCK:
        cached = _metrics_cache.get(key)
        if cached is not None and requested_columns.issubset(cached.columns):
            _metrics_cache.move_to_end(key)
            metrics = cached
        else:
            load_columns = requested_columns | (
                set(cached.columns) if cached is not None else set()
            )
            metrics = _read_grid_export_metrics(
                path,
                region_id=region_id,
                season_year=season_year,
                resolution_m=resolution_m,
                requested_columns=load_columns,
            )
            _metrics_cache[key] = metrics
            _metrics_cache.move_to_end(key)
            while len(_metrics_cache) > _CACHE_SIZE:
                _metrics_cache.popitem(last=False)

    missing_columns = set(required_columns) - metrics.columns
    if missing_columns:
        raise GridExportError(
            f"Cached grid export {path.name} is missing columns: "
            f"{', '.join(sorted(missing_columns))}."
        )
    return metrics


def clear_grid_export_metrics_cache() -> None:
    with _CACHE_LOCK:
        _metrics_cache.clear()
        _region_metrics_cache.clear()


def read_region_csv_metrics(
    path: Path,
    *,
    include_heat_risk: bool = False,
) -> RegionCsvMetrics | None:
    if not path.is_file():
        return None
    try:
        stat = path.stat()
        key = (str(path.resolve()), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
    except OSError as exc:
        raise GridExportError(
            f"Could not inspect cached grid export {path.name}: {exc}"
        ) from exc

    with _CACHE_LOCK:
        cached = _region_metrics_cache.get(key)
        if cached is not None and (
            not include_heat_risk or cached.heat_risk_calculated
        ):
            _region_metrics_cache.move_to_end(key)
            return cached
        metrics = _read_region_csv_metrics(
            path,
            include_heat_risk=include_heat_risk,
        )
        _region_metrics_cache[key] = metrics
        _region_metrics_cache.move_to_end(key)
        while len(_region_metrics_cache) > _REGION_CACHE_SIZE:
            _region_metrics_cache.popitem(last=False)
        return metrics


def _read_region_csv_metrics(
    path: Path,
    *,
    include_heat_risk: bool,
) -> RegionCsvMetrics:
    try:
        selected_columns = set(_RISK_COLUMNS) | {"ndvi_valid"}
        frame = pd.read_csv(
            path,
            usecols=lambda column: column in selected_columns,
        )
    except (
        OSError,
        ValueError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
    ) as exc:
        raise GridExportError(
            f"Could not read cached grid export {path.name}: {exc}"
        ) from exc

    ndvi_mean = None
    if "ndvi" in frame:
        values = pd.to_numeric(frame["ndvi"], errors="coerce")
        valid = np.isfinite(values) & values.between(-1, 1)
        if "ndvi_valid" in frame:
            valid &= frame["ndvi_valid"].astype(str).str.casefold() != "false"
        selected = [float(value) for value in values[valid].tolist()]
        if selected:
            ndvi_mean = sum(selected) / len(selected)

    people_exposed = None
    high_risk_cells = None
    heat_risk_calculated = include_heat_risk
    if include_heat_risk and set(_RISK_COLUMNS).issubset(frame.columns):
        people_exposed, high_risk_cells = calculate_heat_risk(frame)

    return RegionCsvMetrics(
        columns=frozenset(frame.columns),
        ndvi_mean=ndvi_mean,
        heat_risk_calculated=heat_risk_calculated,
        people_exposed_high_heat=people_exposed,
        high_risk_cell_count=high_risk_cells,
    )


def _read_grid_export_metrics(
    path: Path,
    *,
    region_id: str,
    season_year: int,
    resolution_m: int,
    requested_columns: set[str],
) -> GridExportMetrics:
    try:
        selected_columns = requested_columns | {
            "region_id",
            "season_year",
            "resolution_m",
        }
        frame = pd.read_csv(
            path,
            usecols=lambda column: column in selected_columns,
        )
    except (
        OSError,
        ValueError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
    ) as exc:
        raise GridExportError(
            f"Could not read cached grid export {path.name}: {exc}"
        ) from exc

    metadata_matches = (
        ("region_id" not in frame or set(frame["region_id"].astype(str)) == {region_id})
        and (
            "season_year" not in frame
            or set(pd.to_numeric(frame["season_year"], errors="coerce"))
            == {season_year}
        )
        and (
            "resolution_m" not in frame
            or set(pd.to_numeric(frame["resolution_m"], errors="coerce"))
            == {resolution_m}
        )
    )
    if not frame.empty and not metadata_matches:
        raise GridExportError(
            f"Cached grid export {path.name} contains mismatched region, season, "
            "or resolution metadata."
        )

    lst = _metric_summary(frame, "lst_c", 0, 80)
    ndvi = _metric_summary(frame, "ndvi", -1, 1)
    ndbi = _metric_summary(frame, "ndbi", -1, 1)
    ndwi = _metric_summary(frame, "ndwi", -1, 1)
    population_valid_count: int | None = None
    estimated_population: float | None = None
    if "population_estimated_2025" in frame:
        population_values = pd.to_numeric(
            frame["population_estimated_2025"],
            errors="coerce",
        )
        valid_population = population_values[
            np.isfinite(population_values) & (population_values >= 0)
        ]
        population_valid_count = len(valid_population)
        estimated_population = float(valid_population.sum())

    people_exposed: float | None = None
    high_risk_cells: int | None = None
    if set(_RISK_COLUMNS).issubset(frame.columns):
        people_exposed, high_risk_cells = calculate_heat_risk(frame)

    return GridExportMetrics(
        columns=frozenset(requested_columns & set(frame.columns)),
        grid_cell_count=len(frame),
        lst=lst,
        lst_finite_mean=_finite_mean(frame, "lst_c"),
        ndvi=ndvi,
        ndbi=ndbi,
        ndwi=ndwi,
        population_valid_cell_count=population_valid_count,
        estimated_population_2025=estimated_population,
        people_exposed_high_heat=people_exposed,
        high_risk_cell_count=high_risk_cells,
    )


def _metric_summary(
    frame: pd.DataFrame,
    column: str,
    lower: float,
    upper: float,
) -> MetricSummary | None:
    if column not in frame:
        return None
    values = pd.to_numeric(frame[column], errors="coerce")
    valid = values[np.isfinite(values) & values.between(lower, upper)]
    return MetricSummary(
        valid_cell_count=len(valid),
        mean=float(valid.mean()) if not valid.empty else None,
        maximum=float(valid.max()) if not valid.empty else None,
    )


def _finite_mean(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame:
        return None
    values = pd.to_numeric(frame[column], errors="coerce")
    valid = values[np.isfinite(values)]
    return float(valid.mean()) if not valid.empty else None


def calculate_heat_risk(
    cells: pd.DataFrame,
) -> tuple[float | None, int | None]:
    valid = cells.loc[:, _RISK_COLUMNS].replace([np.inf, -np.inf], np.nan).dropna()
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

