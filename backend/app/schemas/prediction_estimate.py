from typing import Literal

from pydantic import BaseModel


class PredictionInput(BaseModel):
    feature: Literal["ndvi", "ndbi"]
    label: str
    value: float | None
    source: str
    resolution_m: int | None
    composite_start: str | None
    composite_end: str | None
    reason: str | None


class PredictionFeatureImportance(BaseModel):
    feature: Literal["ndvi", "ndbi"]
    label: str
    standardized_coefficient: float | None
    relative_importance_percent: float | None
    source: str
    resolution_m: int | None


class PredictionEstimate(BaseModel):
    region_id: str
    season_year: int
    model_status: Literal["available", "unavailable"]
    output_label: Literal["estimate"] = "estimate"
    forecast_label: Literal["not_a_forecast"] = "not_a_forecast"
    model_name: str
    target: str
    target_source: str
    validation_method: str
    training_districts: list[str]
    test_districts: list[str]
    training_cell_count: int
    test_cell_count: int
    training_district_count: int
    test_district_count: int
    r_squared: float | None
    mean_absolute_error_c: float | None
    p90_absolute_error_c: float | None
    evaluation_resolution_m: int | None
    evaluation_start_date: str | None
    evaluation_end_date: str | None
    inputs: list[PredictionInput]
    feature_importance: list[PredictionFeatureImportance]
    model_intercept_c: float | None
    ndvi_coefficient_c_per_index: float | None
    ndbi_coefficient_c_per_index: float | None
    scenario_ndvi_mean: float | None
    scenario_ndbi_mean: float | None
    scenario_baseline_lst_c: float | None
    scenario_error_bound_c: float | None
    scenario_reason: str | None
    reason: str | None
