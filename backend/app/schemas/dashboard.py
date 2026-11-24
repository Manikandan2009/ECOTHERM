from pydantic import BaseModel


class DashboardSummary(BaseModel):
    region_id: str
    season_year: int
    data_status: str
    grid_resolution_m: int | None
    grid_cell_count: int | None
    lst_valid_cell_count: int | None
    lst_coverage_percent: float | None
    lst_mean_c: float | None
    lst_max_c: float | None
    estimated_population_2025: float | None
    population_valid_cell_count: int | None
    population_coverage_percent: float | None
    weather_mean_air_temperature_c: float | None
    weather_max_air_temperature_c: float | None
    weather_model: str | None
    weather_data_status: str | None
    urban_heat_island_intensity_c: float | None = None
    weather_start_date: str | None = None
    weather_end_date: str | None = None
    people_exposed_high_heat: float | None = None
    high_risk_cell_count: int | None = None
    osm_feature_counts: dict[str, int] | None = None
    osm_feature_total: int | None = None
    osm_processed_at_utc: str | None = None
    unavailable_metrics: list[str]
