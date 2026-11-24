import math
from pathlib import Path

from app.repositories.analytics import (
    AnalyticsRepositoryError,
    load_environmental_analytics,
)
from app.schemas.priorities import ConstituencyPriority, PrioritiesResponse

FORMULA = (
    "score (0–100) = 100 × heat exposure percentile (0–1) "
    "× population / maximum cached constituency population "
    "× low-greenness proxy ((1 − NDVI) / 2)"
)
HEAT_METHOD = (
    "Fraction of cached constituency mean LST values less than or equal to this value."
)
POPULATION_METHOD = (
    "WorldPop 2025 constituency estimate divided by the maximum available "
    "constituency estimate."
)
GREEN_METHOD = (
    "Low-greenness proxy = clip((1 − mean Sentinel-2 NDVI) / 2, 0, 1); "
    "this is an index-derived proxy, not a percent green-cover measurement."
)


class PrioritiesRepositoryError(RuntimeError):
    """Raised when cached priority inputs cannot be read."""


def load_constituency_priorities(
    cache_dir: Path,
    *,
    season_year: int,
) -> PrioritiesResponse:
    try:
        analytics = load_environmental_analytics(
            cache_dir,
            season_year=season_year,
        )
    except AnalyticsRepositoryError as exc:
        raise PrioritiesRepositoryError(str(exc)) from exc

    constituencies = [
        region for region in analytics.regions
        if region.region_type == "constituency"
    ]
    valid_lst = sorted(
        region.lst_mean_c
        for region in constituencies
        if region.lst_mean_c is not None and math.isfinite(region.lst_mean_c)
    )
    valid_population = [
        region.population_estimated_2025
        for region in constituencies
        if (
            region.population_estimated_2025 is not None
            and math.isfinite(region.population_estimated_2025)
            and region.population_estimated_2025 > 0
        )
    ]
    max_population = max(valid_population) if valid_population else None

    rows: list[ConstituencyPriority] = []
    for region in constituencies:
        heat_percentile = (
            sum(value <= region.lst_mean_c for value in valid_lst) / len(valid_lst)
            if region.lst_mean_c is not None and valid_lst
            else None
        )
        population_weight = (
            region.population_estimated_2025 / max_population
            if (
                region.population_estimated_2025 is not None
                and region.population_estimated_2025 >= 0
                and max_population is not None
            )
            else None
        )
        low_green = (
            min(1.0, max(0.0, (1 - region.ndvi_mean) / 2))
            if region.ndvi_mean is not None
            else None
        )
        reasons = []
        if heat_percentile is None:
            reasons.append(region.lst_reason or "No valid cached LST mean is available.")
        if population_weight is None:
            reasons.append(
                region.population_reason
                or "No positive WorldPop population estimate is available."
            )
        if low_green is None:
            reasons.append(region.ndvi_reason or "No valid cached NDVI mean is available.")
        score = (
            100 * heat_percentile * population_weight * low_green
            if heat_percentile is not None
            and population_weight is not None
            and low_green is not None
            else None
        )
        if score is not None and not math.isfinite(score):
            score = None
            reasons.append("Priority calculation returned a non-finite value.")
        rows.append(
            ConstituencyPriority(
                constituency_id=region.region_id,
                constituency_name=region.region_name,
                district_id=region.district_id,
                district_name=region.district_name,
                data_status="available" if score is not None else "unavailable",
                lst_mean_c=region.lst_mean_c,
                population_estimated_2025=region.population_estimated_2025,
                ndvi_mean=region.ndvi_mean,
                heat_exposure_percentile=heat_percentile,
                population_weight=population_weight,
                low_green_score=low_green,
                priority_score=score,
                resolution_m=region.resolution_m,
                composite_start=region.composite_start,
                composite_end=region.composite_end,
                lst_reason=region.lst_reason,
                population_reason=region.population_reason,
                ndvi_reason=region.ndvi_reason,
                priority_reason=" ".join(reasons) if reasons else None,
            )
        )

    rows.sort(
        key=lambda item: (
            item.priority_score is None,
            -(item.priority_score or 0),
            item.constituency_name.casefold(),
        )
    )
    available_count = sum(item.priority_score is not None for item in rows)
    data_status = (
        "unavailable"
        if available_count == 0
        else "available"
        if available_count == len(rows)
        else "partial"
    )
    return PrioritiesResponse(
        season_year=season_year,
        data_status=data_status,
        formula=FORMULA,
        heat_exposure_method=HEAT_METHOD,
        population_method=POPULATION_METHOD,
        low_green_method=GREEN_METHOD,
        lst_source=analytics.lst_source,
        population_source=analytics.population_source,
        ndvi_source=analytics.ndvi_source,
        priorities=rows,
    )
