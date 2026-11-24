from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class InspectMetric(BaseModel):
    value: float | None
    status: Literal["available", "unavailable"]
    reason: str | None = None


class RegionalAirTemperature(BaseModel):
    temperature_2m_c: float | None
    status: Literal["live", "stale", "unavailable"]
    updated_at_utc: datetime | None
    spatial_support: str = "Regional Open-Meteo grid estimate (about 10 km); not a cell measurement"
    reason: str | None = None


class MapInspectionResponse(BaseModel):
    latitude: float
    longitude: float
    study_area_status: Literal["inside", "outside"]
    district_id: str | None = None
    district_name: str | None = None
    constituency_id: str | None = None
    constituency_name: str | None = None
    cell_id: str | None = None
    cell_resolution_m: int | None = None
    cell_outline: dict | None = None
    lst_c: InspectMetric
    lst_source: str = "Landsat 8/9 Collection 2 Level 2 L2SP ST_B10; seasonal median"
    lst_composite_start: str | None = None
    lst_composite_end: str | None = None
    lst_valid_observations: InspectMetric
    lst_observation_count_note: str | None = None
    constituency_mean_lst_c: InspectMetric
    constituency_mean_resolution_m: int | None = None
    difference_from_constituency_mean_c: InspectMetric
    population_estimated_2025: InspectMetric
    air_temperature: RegionalAirTemperature
