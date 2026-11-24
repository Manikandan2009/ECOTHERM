from typing import Literal

from pydantic import BaseModel


class SatelliteScatterPoint(BaseModel):
    ndvi: float
    lst_c: float


class SatelliteScatterSummary(BaseModel):
    constituency_id: str
    season_year: int
    data_status: Literal["available", "unavailable"]
    resolution_m: int | None
    pair_count: int
    correlation_pearson: float | None
    composite_start: str | None
    composite_end: str | None
    ndvi_source: str = "Sentinel-2 SR Harmonized, SCL-masked seasonal median"
    lst_source: str = "Landsat 8/9 Collection 2 Level 2 L2SP seasonal median"
    reason: str | None
    points: list[SatelliteScatterPoint]


class SatelliteMetric(BaseModel):
    mean: float | None
    valid_cell_count: int | None
    coverage_percent: float | None


class SatelliteAnalysisSummary(BaseModel):
    region_id: str
    season_year: int
    data_status: Literal["available", "partial", "unavailable"]
    grid_cell_count: int | None
    grid_resolution_m: int | None
    lst: SatelliteMetric
    ndvi: SatelliteMetric
    ndbi: SatelliteMetric
    ndwi: SatelliteMetric
    composite_start: str | None
    composite_end: str | None
    lst_source: str = "Landsat 8/9 Collection 2 Level 2 L2SP ST_B10"
    optical_source: str = "Sentinel-2 SR Harmonized; SCL cloud masked"
