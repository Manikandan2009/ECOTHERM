import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import httpx


class LiveWeatherError(RuntimeError):
    """Raised when current weather cannot be acquired and no cache exists."""


def district_centroid(cache_dir: Path, district_id: str) -> tuple[str, float, float]:
    districts_path = cache_dir / "processed" / "boundaries" / "districts.geojson"
    districts = gpd.read_file(districts_path)
    matches = districts[districts["district_id"].astype(str) == district_id]
    if len(matches) != 1:
        raise LiveWeatherError(f"Unknown district ID: {district_id}")
    district = matches.iloc[0]
    centroid = districts.to_crs("EPSG:6933").loc[matches.index[0]].geometry.centroid
    point = gpd.GeoSeries([centroid], crs="EPSG:6933").to_crs("EPSG:4326").iloc[0]
    return str(district["district_name"]), float(point.y), float(point.x)


def constituency_centroid(
    cache_dir: Path,
    constituency_id: str,
) -> tuple[str, float, float]:
    path = cache_dir / "processed" / "boundaries" / "constituencies.geojson"
    try:
        constituencies = gpd.read_file(path)
    except (OSError, ValueError) as exc:
        raise LiveWeatherError(f"Could not read constituency boundaries: {exc}") from exc
    matches = constituencies[
        constituencies["constituency_id"].astype(str) == constituency_id
    ]
    if len(matches) != 1:
        raise LiveWeatherError(f"Unknown constituency ID: {constituency_id}")
    projected = matches.to_crs("EPSG:6933")
    point = (
        gpd.GeoSeries([projected.iloc[0].geometry.centroid], crs="EPSG:6933")
        .to_crs("EPSG:4326")
        .iloc[0]
    )
    return (
        str(matches.iloc[0]["constituency_name"]),
        float(point.y),
        float(point.x),
    )


async def fetch_live_district_weather(
    *,
    cache_dir: Path,
    district_id: str,
    timeout_seconds: float = 30,
) -> dict[str, Any]:
    district_name, latitude, longitude = district_centroid(cache_dir, district_id)
    cache_path = cache_dir / "processed" / "live_weather" / f"{district_id}.json"
    return await _fetch_live_weather(
        cache_path=cache_path,
        region_id=district_id,
        region_name=district_name,
        latitude=latitude,
        longitude=longitude,
        region_type="district",
        timeout_seconds=timeout_seconds,
    )


async def fetch_live_constituency_weather(
    *,
    cache_dir: Path,
    constituency_id: str,
    timeout_seconds: float = 30,
) -> dict[str, Any]:
    constituency_name, latitude, longitude = constituency_centroid(
        cache_dir,
        constituency_id,
    )
    cache_path = (
        cache_dir
        / "processed"
        / "live_weather"
        / "constituencies"
        / f"{constituency_id}.json"
    )
    return await _fetch_live_weather(
        cache_path=cache_path,
        region_id=constituency_id,
        region_name=constituency_name,
        latitude=latitude,
        longitude=longitude,
        region_type="constituency",
        timeout_seconds=timeout_seconds,
    )


async def _fetch_live_weather(
    *,
    cache_path: Path,
    region_id: str,
    region_name: str,
    latitude: float,
    longitude: float,
    region_type: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cached = _read_cache(cache_path)
    if cached is not None:
        age_seconds = time.time() - float(cached["_fetched_epoch"])
        if age_seconds < 900:
            return dict(cached)

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "timezone": "Asia/Kolkata",
    }
    last_error: str | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params=params,
                )
                response.raise_for_status()
                payload = response.json()
            current = payload.get("current")
            if not isinstance(current, dict):
                raise LiveWeatherError("Open-Meteo forecast response has no current-weather block.")
            now = datetime.now(timezone.utc)
            result = {
                f"{region_type}_id": region_id,
                f"{region_type}_name": region_name,
                "temperature_2m_c": current.get("temperature_2m"),
                "relative_humidity_2m_percent": current.get("relative_humidity_2m"),
                "wind_speed_10m_kmh": current.get("wind_speed_10m"),
                "status": "live",
                "updated_at_utc": now.isoformat(),
                "provider": "Open-Meteo Forecast API",
                "data_status": "current_estimate",
                "error": None,
                "_fetched_epoch": time.time(),
            }
            cache_path.write_text(
                json.dumps(result, indent=2),
                encoding="utf-8",
            )
            return result
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, LiveWeatherError) as exc:
            last_error = str(exc)
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)

    if cached is not None:
        stale = dict(cached)
        stale["status"] = "stale"
        stale["data_status"] = "cached_estimate"
        stale["error"] = f"Open-Meteo refresh failed after 3 attempts: {last_error}"
        return stale
    return {
        f"{region_type}_id": region_id,
        f"{region_type}_name": region_name,
        "temperature_2m_c": None,
        "relative_humidity_2m_percent": None,
        "wind_speed_10m_kmh": None,
        "status": "unavailable",
        "updated_at_utc": None,
        "provider": "Open-Meteo Forecast API",
        "data_status": "missing",
        "error": f"Open-Meteo refresh failed after 3 attempts: {last_error}",
    }


def _read_cache(cache_path: Path) -> dict[str, Any] | None:
    if not cache_path.is_file():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        if "_fetched_epoch" not in payload:
            return None
        return payload
    except (OSError, json.JSONDecodeError):
        return None
