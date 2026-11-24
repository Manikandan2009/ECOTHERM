from datetime import date

import httpx
import pytest
import respx

from app.api.v1 import weather as weather_routes
from app.core.settings import Settings
from app.main import app

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
    "daily": {
        "time": ["2026-04-01"],
        "temperature_2m_max": [34.0],
        "temperature_2m_min": [25.0],
        "temperature_2m_mean": [29.5],
        "wind_speed_10m_max": [18.0],
    },
    "hourly_units": {
        "time": "iso8601",
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "wind_speed_10m": "km/h",
    },
    "hourly": {
        "time": ["2026-04-01T00:00"],
        "temperature_2m": [25.8],
        "relative_humidity_2m": [84],
        "wind_speed_10m": [10.0],
    },
}


@pytest.mark.asyncio
@respx.mock
async def test_weather_endpoint_returns_provenance_backed_response(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    respx.get(ARCHIVE_URL).mock(
        return_value=httpx.Response(200, json=PROVIDER_FIXTURE)
    )
    settings = Settings(
        cache_dir=tmp_path,
        open_meteo_archive_url=ARCHIVE_URL,
    )
    monkeypatch.setattr(weather_routes, "get_settings", lambda: settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/weather/point",
            params={
                "location_id": "Chennai",
                "latitude": 13.0827,
                "longitude": 80.2707,
                "start_date": "2026-04-01",
                "end_date": "2026-04-01",
            },
        )

    assert response.status_code == 200
    result = response.json()
    assert result["daily"]["temperature_2m_mean"] == [29.5]
    assert result["hourly"]["relative_humidity_2m"] == [84]
    assert result["provenance"]["data_status"] == "reanalysis_estimate"
    assert result["provenance"]["missing_dates"] == []


@pytest.mark.asyncio
async def test_weather_endpoint_rejects_reversed_period(tmp_path, monkeypatch) -> None:
    settings = Settings(
        cache_dir=tmp_path,
        open_meteo_archive_url=ARCHIVE_URL,
    )
    monkeypatch.setattr(weather_routes, "get_settings", lambda: settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/api/v1/weather/point",
            params={
                "location_id": "Chennai",
                "latitude": 13.08,
                "longitude": 80.27,
                "start_date": date(2026, 6, 30).isoformat(),
                "end_date": date(2026, 4, 1).isoformat(),
            },
        )

    assert response.status_code == 422
    assert "end_date" in response.json()["detail"]
