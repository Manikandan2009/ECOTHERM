from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.core.settings import get_settings
from app.schemas.weather import WeatherResponse
from app.schemas.weather import LiveWeatherResponse
from app.services.open_meteo import (
    OpenMeteoClient,
    OpenMeteoProviderError,
    WeatherCacheError,
)
from app.services.live_weather import (
    LiveWeatherError,
    fetch_live_constituency_weather,
    fetch_live_district_weather,
)

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])


@router.get("/live", response_model=LiveWeatherResponse)
async def get_live_district_weather(
    district_id: Annotated[str | None, Query(pattern=r"^[a-z0-9_]+$")] = None,
    constituency_id: Annotated[str | None, Query(pattern=r"^ac_[a-z0-9_]+$")] = None,
) -> LiveWeatherResponse:
    if bool(district_id) == bool(constituency_id):
        raise HTTPException(
            status_code=422,
            detail="Provide exactly one of district_id or constituency_id.",
        )
    settings = get_settings()
    try:
        if constituency_id:
            payload = await fetch_live_constituency_weather(
                cache_dir=settings.cache_dir,
                constituency_id=constituency_id,
                timeout_seconds=settings.open_meteo_timeout_seconds,
            )
        else:
            payload = await fetch_live_district_weather(
                cache_dir=settings.cache_dir,
                district_id=str(district_id),
                timeout_seconds=settings.open_meteo_timeout_seconds,
            )
    except LiveWeatherError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LiveWeatherResponse.model_validate(payload)


@router.get("/point", response_model=WeatherResponse)
async def get_point_weather(
    location_id: Annotated[str, Query(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,59}$")],
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    start_date: date,
    end_date: date,
    force_refresh: bool = False,
) -> WeatherResponse:
    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="end_date must be on or after start_date",
        )
    settings = get_settings()
    client = OpenMeteoClient(
        archive_url=settings.open_meteo_archive_url,
        cache_dir=settings.cache_dir,
        timeout_seconds=settings.open_meteo_timeout_seconds,
    )
    try:
        result = await client.fetch_daily(
            location_id=location_id,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
            force_refresh=force_refresh,
        )
    except OpenMeteoProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except WeatherCacheError as exc:
        raise HTTPException(
            status_code=500,
            detail="Open-Meteo data was acquired but could not be safely read or cached.",
        ) from exc
    return result.data
