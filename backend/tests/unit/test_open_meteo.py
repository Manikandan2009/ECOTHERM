from datetime import date

import httpx
import pytest
import respx

from app.schemas.weather import WeatherRequest
from app.services.open_meteo import (
    OpenMeteoClient,
    OpenMeteoProviderError,
    WeatherCacheError,
)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# This fixture is fabricated test input only; it is never used as project data.
PROVIDER_FIXTURE = {
    "latitude": 13.0,
    "longitude": 80.25,
    "elevation": 10.0,
    "timezone": "Asia/Kolkata",
    "timezone_abbreviation": "GMT+5:30",
    "utc_offset_seconds": 19800,
    "daily_units": {
        "time": "iso8601",
        "temperature_2m_max": "°C",
        "temperature_2m_min": "°C",
        "temperature_2m_mean": "°C",
        "wind_speed_10m_max": "km/h",
    },
    "hourly_units": {
        "time": "iso8601",
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "wind_speed_10m": "km/h",
    },
    "daily": {
        "time": ["2026-04-01", "2026-04-02"],
        "temperature_2m_max": [34.0, None],
        "temperature_2m_min": [25.0, 25.5],
        "temperature_2m_mean": [29.5, 30.0],
        "wind_speed_10m_max": [18.0, None],
    },
    "hourly": {
        "time": ["2026-04-01T00:00", "2026-04-01T01:00"],
        "temperature_2m": [25.8, 25.5],
        "relative_humidity_2m": [84, 86],
        "wind_speed_10m": [10.0, 9.0],
    },
}


def make_client(tmp_path) -> OpenMeteoClient:
    return OpenMeteoClient(ARCHIVE_URL, tmp_path / "cache")


@pytest.mark.asyncio
@respx.mock
async def test_fetches_validates_and_caches_weather_response(tmp_path) -> None:
    route = respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(200, json=PROVIDER_FIXTURE)
    )
    client = make_client(tmp_path)
    request = {
        "location_id": "Chennai",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "start_date": date(2026, 4, 1),
        "end_date": date(2026, 6, 30),
    }

    fresh = await client.fetch_daily(**request)
    cached = await client.fetch_daily(**request)

    assert route.call_count == 1
    assert route.calls[0].request.url.params["models"] == "era5_land"
    assert route.calls[0].request.url.params["timezone"] == "Asia/Kolkata"
    assert route.calls[0].request.url.params["hourly"] == (
        "temperature_2m,relative_humidity_2m,wind_speed_10m"
    )
    assert fresh.from_cache is False
    assert fresh.data.daily.temperature_2m_max == [34.0, None]
    assert fresh.data.hourly.relative_humidity_2m == [84, 86]
    assert fresh.data.hourly.wind_speed_10m == [10.0, 9.0]
    assert fresh.data.provenance.data_status == "reanalysis_estimate"
    assert fresh.data.provenance.requested_latitude == 13.0827
    assert fresh.data.provenance.expected_daily_count == 91
    assert fresh.data.provenance.returned_daily_count == 2
    assert fresh.data.provenance.expected_hourly_count == 2184
    assert fresh.data.provenance.returned_hourly_count == 2
    assert fresh.data.provenance.missing_value_counts["daily.temperature_2m_max"] == 1
    assert fresh.path.is_file()
    assert fresh.daily_csv_path.is_file()
    assert fresh.hourly_csv_path.is_file()
    assert fresh.daily_csv_path.read_text(encoding="utf-8").splitlines()[1].startswith(
        "2026-04-01,Chennai,"
    )
    assert "relative_humidity_2m_percent" in fresh.hourly_csv_path.read_text(
        encoding="utf-8"
    ).splitlines()[0]
    assert cached.from_cache is True
    assert cached.daily_csv_path == fresh.daily_csv_path
    assert cached.data == fresh.data


@pytest.mark.asyncio
@respx.mock
async def test_provider_http_error_is_not_converted_to_empty_data(tmp_path) -> None:
    respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(503, text="temporarily unavailable")
    )
    client = make_client(tmp_path)

    with pytest.raises(OpenMeteoProviderError, match="HTTP 503"):
        await client.fetch_daily(
            location_id="Madurai",
            latitude=9.9252,
            longitude=78.1198,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 2),
        )


@pytest.mark.asyncio
async def test_invalid_date_range_is_rejected_before_network_request(tmp_path) -> None:
    client = make_client(tmp_path)

    with pytest.raises(ValueError, match="end_date must be on or after start_date"):
        await client.fetch_daily(
            location_id="Coimbatore",
            latitude=11.0168,
            longitude=76.9558,
            start_date=date(2026, 6, 30),
            end_date=date(2026, 4, 1),
        )


def test_request_validation_rejects_path_like_location_id() -> None:
    with pytest.raises(ValueError):
        WeatherRequest(
            location_id="../chennai",
            latitude=13.08,
            longitude=80.27,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 6, 30),
        )


@pytest.mark.asyncio
async def test_corrupt_cache_is_reported_without_silent_refetch(tmp_path) -> None:
    client = make_client(tmp_path)
    request = WeatherRequest(
        location_id="Chennai",
        latitude=13.08,
        longitude=80.27,
        start_date=date(2026, 4, 1),
        end_date=date(2026, 6, 30),
    )
    cache_path = client._cache_path(request)
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(WeatherCacheError, match="force-refresh"):
        await client.fetch_daily(
            location_id=request.location_id,
            latitude=request.latitude,
            longitude=request.longitude,
            start_date=request.start_date,
            end_date=request.end_date,
        )
