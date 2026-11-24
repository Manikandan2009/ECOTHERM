from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WeatherRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    location_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,59}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_date_range(self) -> "WeatherRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class WeatherDaily(BaseModel):
    time: list[date]
    temperature_2m_max: list[float | None]
    temperature_2m_min: list[float | None]
    temperature_2m_mean: list[float | None]
    wind_speed_10m_max: list[float | None]

    @model_validator(mode="after")
    def validate_aligned_series(self) -> "WeatherDaily":
        lengths = {
            len(self.time),
            len(self.temperature_2m_max),
            len(self.temperature_2m_min),
            len(self.temperature_2m_mean),
            len(self.wind_speed_10m_max),
        }
        if len(lengths) != 1:
            raise ValueError("weather daily arrays must have matching lengths")
        if self.time != sorted(set(self.time)):
            raise ValueError("weather daily dates must be unique and increasing")
        return self


class WeatherHourly(BaseModel):
    time: list[datetime]
    temperature_2m: list[float | None]
    relative_humidity_2m: list[float | None]
    wind_speed_10m: list[float | None]

    @model_validator(mode="after")
    def validate_aligned_series(self) -> "WeatherHourly":
        lengths = {
            len(self.time),
            len(self.temperature_2m),
            len(self.relative_humidity_2m),
            len(self.wind_speed_10m),
        }
        if len(lengths) != 1:
            raise ValueError("weather hourly arrays must have matching lengths")
        if self.time != sorted(set(self.time)):
            raise ValueError("weather hourly timestamps must be unique and increasing")
        return self


class WeatherProvenance(BaseModel):
    provider: Literal["Open-Meteo Historical Weather API"] = "Open-Meteo Historical Weather API"
    endpoint: str
    model: str
    requested_at_utc: datetime
    requested_latitude: float
    requested_longitude: float
    requested_start_date: date
    requested_end_date: date
    missing_dates: list[date]
    expected_daily_count: int
    returned_daily_count: int
    expected_hourly_count: int
    returned_hourly_count: int
    missing_value_counts: dict[str, int]
    spatial_support: str = "ERA5-Land reanalysis; approximately 0.1 degree, not 100 m observations"
    data_status: Literal["reanalysis_estimate"] = "reanalysis_estimate"
    attribution: str = "Weather data by Open-Meteo; CC BY 4.0 attribution applies."


class WeatherResponse(BaseModel):
    location_id: str
    latitude: float
    longitude: float
    elevation: float | None = None
    timezone: str
    timezone_abbreviation: str
    utc_offset_seconds: int
    daily_units: dict[str, str]
    daily: WeatherDaily
    hourly_units: dict[str, str]
    hourly: WeatherHourly
    provenance: WeatherProvenance

    @model_validator(mode="after")
    def validate_requested_period(self) -> "WeatherResponse":
        start = self.provenance.requested_start_date
        end = self.provenance.requested_end_date
        if any(day < start or day > end for day in self.daily.time):
            raise ValueError("provider returned a date outside the requested period")
        if any(timestamp.date() < start or timestamp.date() > end for timestamp in self.hourly.time):
            raise ValueError("provider returned an hourly timestamp outside the requested period")
        if end < start:
            raise ValueError("requested end date must be on or after start date")
        expected = {
            date.fromordinal(ordinal)
            for ordinal in range(start.toordinal(), end.toordinal() + 1)
        }
        returned = set(self.daily.time)
        actual_missing = sorted(expected - returned)
        if self.provenance.missing_dates != actual_missing:
            raise ValueError("provenance missing_dates must match the returned daily dates")
        expected_day_count = (end - start).days + 1
        if self.provenance.expected_daily_count != expected_day_count:
            raise ValueError("provenance expected_daily_count does not match the requested period")
        if self.provenance.returned_daily_count != len(self.daily.time):
            raise ValueError("provenance returned_daily_count does not match the daily data")
        if self.provenance.expected_hourly_count != expected_day_count * 24:
            raise ValueError("provenance expected_hourly_count does not match the requested period")
        if self.provenance.returned_hourly_count != len(self.hourly.time):
            raise ValueError("provenance returned_hourly_count does not match the hourly data")
        return self


class LiveWeatherResponse(BaseModel):
    district_id: str | None = None
    district_name: str | None = None
    constituency_id: str | None = None
    constituency_name: str | None = None
    temperature_2m_c: float | None
    relative_humidity_2m_percent: float | None
    wind_speed_10m_kmh: float | None
    status: Literal["live", "stale", "unavailable"]
    updated_at_utc: datetime | None
    provider: Literal["Open-Meteo Forecast API"] = "Open-Meteo Forecast API"
    data_status: Literal["current_estimate", "cached_estimate", "missing"] = "current_estimate"
    error: str | None = None

    @model_validator(mode="after")
    def validate_region_identity(self) -> "LiveWeatherResponse":
        if not (
            self.district_id and self.district_name
            or self.constituency_id and self.constituency_name
        ):
            raise ValueError("live weather must identify its district or constituency")
        return self
