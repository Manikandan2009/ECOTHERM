from typing import Literal

from pydantic import BaseModel


class AnalyticsRegion(BaseModel):
    region_id: str
    region_name: str
    region_type: Literal["district", "constituency"]
    district_id: str
    district_name: str
    data_status: Literal["available", "partial", "unavailable"]
    cell_count: int | None
    lst_mean_c: float | None
    lst_coverage_percent: float | None
    population_estimated_2025: float | None
    ndvi_mean: float | None
    resolution_m: int | None
    composite_start: str | None
    composite_end: str | None
    lst_reason: str | None
    population_reason: str | None
    ndvi_reason: str | None
    air_temperature_mean_c: float | None
    air_temperature_model: str | None
    air_temperature_start_date: str | None
    air_temperature_end_date: str | None
    air_temperature_reason: str | None


class AnalyticsResponse(BaseModel):
    season_year: int
    data_status: Literal["available", "partial", "unavailable"]
    lst_source: str
    population_source: str
    ndvi_source: str
    air_temperature_source: str
    regions: list[AnalyticsRegion]
