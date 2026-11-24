from typing import Literal

from pydantic import BaseModel


class PredictionStatus(BaseModel):
    region_id: str
    status: Literal["unavailable"] = "unavailable"
    model_status: Literal["no_qualified_model"] = "no_qualified_model"
    prediction_available: bool = False
    available_season_years: list[int]
    region_season_years: list[int]
    latest_region_cell_count: int | None
    latest_region_lst_valid_cell_count: int | None
    target_status: Literal["not_defined"] = "not_defined"
    baseline_status: Literal["not_evaluated"] = "not_evaluated"
    spatial_validation_status: Literal["not_run"] = "not_run"
    temporal_validation_status: Literal["not_run"] = "not_run"
    reason: str
