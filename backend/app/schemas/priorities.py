from pydantic import BaseModel


class ConstituencyPriority(BaseModel):
    constituency_id: str
    constituency_name: str
    district_id: str
    district_name: str
    data_status: str
    lst_mean_c: float | None
    population_estimated_2025: float | None
    ndvi_mean: float | None
    heat_exposure_percentile: float | None
    population_weight: float | None
    low_green_score: float | None
    priority_score: float | None
    resolution_m: int | None
    composite_start: str | None
    composite_end: str | None
    lst_reason: str | None
    population_reason: str | None
    ndvi_reason: str | None
    priority_reason: str | None


class PrioritiesResponse(BaseModel):
    season_year: int
    data_status: str
    formula: str
    heat_exposure_method: str
    population_method: str
    low_green_method: str
    lst_source: str
    population_source: str
    ndvi_source: str
    priorities: list[ConstituencyPriority]
