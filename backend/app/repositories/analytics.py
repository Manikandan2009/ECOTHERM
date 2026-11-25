import json
import math
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.repositories.constituencies import (
    ConstituencyBoundaryError,
    load_constituencies,
)
from app.repositories.districts import DistrictBoundaryError, load_district_boundaries
from app.repositories.grid_metrics import GridExportError, read_region_csv_metrics
from app.repositories.weather_cache import load_cached_weather_summary
from app.schemas.analytics import AnalyticsRegion, AnalyticsResponse

LST_SOURCE = "Landsat 8/9 Collection 2 Level 2 L2SP ST_B10"
POPULATION_SOURCE = "WorldPop 2025 gridded population, modelled estimate"
NDVI_SOURCE = "Sentinel-2 SR Harmonized NDVI mean; vegetation greenness proxy, not percent cover"
AIR_TEMPERATURE_SOURCE = (
    "Open-Meteo ERA5-Land daily reanalysis estimate; "
    "0.1° (~11 km) model grid; regional context only"
)
_ANALYTICS_CACHE_LOCK = threading.RLock()


class AnalyticsRepositoryError(RuntimeError):
    """Raised when cached analytics or its provenance cannot be read."""


def load_environmental_analytics(
    cache_dir: Path,
    *,
    season_year: int,
) -> AnalyticsResponse:
    dataset_version = _analytics_dataset_version(cache_dir, season_year)
    with _ANALYTICS_CACHE_LOCK:
        result = _load_environmental_analytics_cached(
            str(cache_dir.resolve()),
            season_year,
            dataset_version,
        )
        return result.model_copy(deep=True)


@lru_cache(maxsize=4)
def _load_environmental_analytics_cached(
    cache_dir_string: str,
    season_year: int,
    dataset_version: tuple[tuple[str, int, int, int], ...],
) -> AnalyticsResponse:
    del dataset_version
    return _load_environmental_analytics_uncached(
        Path(cache_dir_string),
        season_year=season_year,
    )


def clear_environmental_analytics_cache() -> None:
    with _ANALYTICS_CACHE_LOCK:
        _load_environmental_analytics_cached.cache_clear()


def _analytics_dataset_version(
    cache_dir: Path,
    season_year: int,
) -> tuple[tuple[str, int, int, int], ...]:
    processed = cache_dir / "processed"
    files = [
        processed / "ecotherm.sqlite",
        processed / "boundaries" / "districts.geojson",
        processed / "boundaries" / "districts_manifest.json",
        processed / "boundaries" / "constituencies.geojson",
        processed / "boundaries" / "constituencies_manifest.json",
    ]
    files.extend((processed / "open_meteo").glob("*_daily.csv"))
    for collection in ("districts", "constituencies"):
        batch_root = processed / collection / "static_batches"
        files.extend(batch_root.glob("*/manifest.json"))
        files.extend(batch_root.glob(f"*/*_{season_year}.csv"))

    version: list[tuple[str, int, int, int]] = []
    for path in sorted(set(files)):
        try:
            stat = path.stat()
            version.append(
                (
                    str(path.relative_to(cache_dir)),
                    stat.st_mtime_ns,
                    stat.st_ctime_ns,
                    stat.st_size,
                )
            )
        except OSError:
            version.append((str(path.relative_to(cache_dir)), -1, -1, -1))
    return tuple(version)


def _load_environmental_analytics_uncached(
    cache_dir: Path,
    *,
    season_year: int,
) -> AnalyticsResponse:
    try:
        districts = load_district_boundaries(cache_dir)["districts"]
        constituencies = load_constituencies(cache_dir)["constituencies"]
    except (DistrictBoundaryError, ConstituencyBoundaryError) as exc:
        raise AnalyticsRepositoryError(str(exc)) from exc

    regions: list[AnalyticsRegion] = []
    district_weather: dict[
        str, tuple[float | None, str | None, str | None, str | None]
    ] = {}
    for district in districts:
        district_id = district["district_id"]
        region = _load_region(
            cache_dir,
            season_year=season_year,
            region_id=district_id,
            region_name=district["district_name"],
            district_id=district_id,
            district_name=district["district_name"],
            region_type="district",
        )
        weather = load_cached_weather_summary(
            cache_dir,
            location_id=f"{district_id}_reference",
            season_year=season_year,
        )
        region.air_temperature_mean_c = weather[0]
        region.air_temperature_model = weather[2]
        region.air_temperature_start_date = weather[4]
        region.air_temperature_end_date = weather[5]
        region.air_temperature_reason = (
            None
            if weather[0] is not None
            else "No cached district-reference air-temperature series is available."
        )
        district_weather[district_id] = (
            weather[0],
            weather[2],
            weather[4],
            weather[5],
        )
        regions.append(region)

    for constituency in constituencies:
        region = _load_region(
            cache_dir,
            season_year=season_year,
            region_id=constituency["constituency_id"],
            region_name=constituency["constituency_name"],
            district_id=constituency["district_id"],
            district_name=constituency["district_name"],
            region_type="constituency",
        )
        district_context = district_weather.get(constituency["district_id"])
        if district_context is not None and district_context[0] is not None:
            (
                region.air_temperature_mean_c,
                region.air_temperature_model,
                region.air_temperature_start_date,
                region.air_temperature_end_date,
            ) = district_context
            region.air_temperature_reason = (
                f"Context from the {constituency['district_name']} district reference "
                "point; not a constituency-specific measurement."
            )
        regions.append(region)

    available_count = sum(region.data_status == "available" for region in regions)
    data_status = (
        "unavailable"
        if available_count == 0
        else "available"
        if available_count == len(regions)
        else "partial"
    )
    return AnalyticsResponse(
        season_year=season_year,
        data_status=data_status,
        lst_source=LST_SOURCE,
        population_source=POPULATION_SOURCE,
        ndvi_source=NDVI_SOURCE,
        air_temperature_source=AIR_TEMPERATURE_SOURCE,
        regions=regions,
    )


def _load_region(
    cache_dir: Path,
    *,
    season_year: int,
    region_id: str,
    region_name: str,
    district_id: str,
    district_name: str,
    region_type: str,
) -> AnalyticsRegion:
    collection_name = "districts" if region_type == "district" else "constituencies"
    directory = (
        cache_dir / "processed" / collection_name / "static_batches" / region_id
    )
    manifest_path = directory / "manifest.json"
    csv_path = directory / f"{region_id}_{season_year}.csv"
    manifest: dict[str, Any] | None = None
    if manifest_path.is_file():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AnalyticsRepositoryError(
                f"Could not read cached analytics manifest for {region_name}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise AnalyticsRepositoryError(
                f"Cached analytics manifest for {region_name} must contain an object."
            )
        if payload.get("season_year") == season_year:
            manifest = payload

    cell_count = _number(manifest, "cell_count" if region_type == "district" else "grid_cell_count")
    lst_valid_count = _number(
        manifest,
        "lst_valid_cells" if region_type == "district" else "lst_valid_cell_count",
    )
    lst_mean = _number(manifest, "lst_mean_c")
    population = _number(
        manifest,
        "worldpop_population_2025"
        if region_type == "district"
        else "population_estimated_2025",
    )
    ndvi_mean = _mean_ndvi(
        csv_path,
        region_name,
        include_heat_risk=region_type == "district",
    )
    lst_coverage = (
        lst_valid_count / cell_count * 100
        if lst_valid_count is not None and cell_count and cell_count > 0
        else None
    )
    start = (
        manifest.get("lst_composite_start")
        or manifest.get("composite_start")
        if manifest
        else None
    )
    end = (
        manifest.get("lst_composite_end")
        or manifest.get("composite_end")
        if manifest
        else None
    )
    available_metrics = sum(
        value is not None for value in (lst_mean, population, ndvi_mean)
    )
    status = (
        "unavailable"
        if available_metrics == 0
        else "available"
        if available_metrics == 3
        else "partial"
    )
    missing_reason = (
        f"No cached {season_year} {region_type} data or provenance manifest is available."
        if manifest is None
        else None
    )
    return AnalyticsRegion(
        region_id=region_id,
        region_name=region_name,
        region_type=region_type,
        district_id=district_id,
        district_name=district_name,
        data_status=status,
        cell_count=int(cell_count) if cell_count is not None else None,
        lst_mean_c=lst_mean,
        lst_coverage_percent=lst_coverage,
        population_estimated_2025=population,
        ndvi_mean=ndvi_mean,
        resolution_m=1000 if manifest is not None else None,
        composite_start=str(start) if start else None,
        composite_end=str(end) if end else None,
        lst_reason=(
            None
            if lst_mean is not None
            else missing_reason or "No valid Landsat LST cells are cached for this composite."
        ),
        population_reason=(
            None
            if population is not None
            else missing_reason or "No valid WorldPop 2025 population estimate is cached."
        ),
        ndvi_reason=(
            None
            if ndvi_mean is not None
            else missing_reason or "No valid Sentinel-2 NDVI cells are cached for this composite."
        ),
        air_temperature_mean_c=None,
        air_temperature_model=None,
        air_temperature_start_date=None,
        air_temperature_end_date=None,
        air_temperature_reason=(
            None
            if region_type == "district"
            else "Air temperature is available only as district-reference context, not a constituency measurement."
        ),
    )


def _mean_ndvi(
    csv_path: Path,
    region_name: str,
    *,
    include_heat_risk: bool = False,
) -> float | None:
    if not csv_path.is_file():
        return None
    try:
        metrics = read_region_csv_metrics(
            csv_path,
            include_heat_risk=include_heat_risk,
        )
    except GridExportError as exc:
        raise AnalyticsRepositoryError(
            f"Could not read cached NDVI cells for {region_name}: {exc}"
        ) from exc
    if metrics is None:
        return None
    if "ndvi" not in metrics.columns:
        raise AnalyticsRepositoryError(
            f"Cached grid CSV for {region_name} is missing the NDVI column."
        )
    return metrics.ndvi_mean


def _number(manifest: dict[str, Any] | None, key: str) -> float | None:
    if manifest is None or manifest.get(key) is None:
        return None
    try:
        value = float(manifest[key])
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None
