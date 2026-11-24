import csv
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from collections.abc import Iterable, Sequence

import httpx
from pydantic import ValidationError

from app.schemas.weather import WeatherRequest, WeatherResponse, WeatherProvenance

DAILY_VARIABLES = (
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "wind_speed_10m_max",
)
HOURLY_VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
)
WEATHER_MODEL = "era5_land"


class OpenMeteoError(RuntimeError):
    """Base error for Open-Meteo requests and local cache handling."""


class OpenMeteoProviderError(OpenMeteoError):
    """Raised when the provider request fails or returns invalid data."""


class WeatherCacheError(OpenMeteoError):
    """Raised when a cached response cannot be read or written."""


@dataclass(frozen=True)
class CachedWeather:
    data: WeatherResponse
    path: Path
    daily_csv_path: Path
    hourly_csv_path: Path
    from_cache: bool


class OpenMeteoClient:
    def __init__(
        self,
        archive_url: str,
        cache_dir: Path,
        timeout_seconds: float = 30.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self.archive_url = archive_url
        self.cache_dir = cache_dir
        self.timeout_seconds = timeout_seconds

    async def fetch_daily(
        self,
        *,
        location_id: str,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        force_refresh: bool = False,
    ) -> CachedWeather:
        request = WeatherRequest(
            location_id=location_id,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
        )
        cache_path = self._cache_path(request)
        if cache_path.exists() and not force_refresh:
            data = self._read_cache(cache_path)
            daily_csv_path, hourly_csv_path = self._write_csv_exports(data, cache_path)
            return CachedWeather(
                data=data,
                path=cache_path,
                daily_csv_path=daily_csv_path,
                hourly_csv_path=hourly_csv_path,
                from_cache=True,
            )

        params = {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "daily": ",".join(DAILY_VARIABLES),
            "hourly": ",".join(HOURLY_VARIABLES),
            "timezone": "Asia/Kolkata",
            "temperature_unit": "celsius",
            "models": WEATHER_MODEL,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = await client.get(self.archive_url, params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300].replace("\n", " ")
            raise OpenMeteoProviderError(
                f"Open-Meteo returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.RequestError as exc:
            raise OpenMeteoProviderError(
                f"Could not reach Open-Meteo: {exc}"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise OpenMeteoProviderError(
                "Open-Meteo returned a response that was not valid JSON."
            ) from exc
        if not isinstance(payload, dict) or "daily" not in payload:
            raise OpenMeteoProviderError(
                "Open-Meteo response did not contain the requested daily data."
            )
        raw_daily = payload["daily"]
        if not isinstance(raw_daily, dict) or not isinstance(raw_daily.get("time"), list):
            raise OpenMeteoProviderError(
                "Open-Meteo daily response did not include a valid date array."
            )
        raw_hourly = payload.get("hourly")
        if not isinstance(raw_hourly, dict) or not isinstance(raw_hourly.get("time"), list):
            raise OpenMeteoProviderError(
                "Open-Meteo hourly response did not include a valid timestamp array."
            )

        try:
            missing_dates = self._missing_dates(
                request.start_date,
                request.end_date,
                raw_daily["time"],
            )
            weather = WeatherResponse(
                location_id=request.location_id,
                latitude=payload["latitude"],
                longitude=payload["longitude"],
                elevation=payload.get("elevation"),
                timezone=payload["timezone"],
                timezone_abbreviation=payload["timezone_abbreviation"],
                utc_offset_seconds=payload["utc_offset_seconds"],
                daily_units=payload["daily_units"],
                daily=payload["daily"],
                hourly_units=payload["hourly_units"],
                hourly=payload["hourly"],
                provenance=WeatherProvenance(
                    endpoint=self.archive_url,
                    model=WEATHER_MODEL,
                    requested_at_utc=datetime.now(timezone.utc),
                    requested_latitude=request.latitude,
                    requested_longitude=request.longitude,
                    requested_start_date=request.start_date,
                    requested_end_date=request.end_date,
                    missing_dates=missing_dates,
                    expected_daily_count=(request.end_date - request.start_date).days + 1,
                    returned_daily_count=len(raw_daily["time"]),
                    expected_hourly_count=((request.end_date - request.start_date).days + 1) * 24,
                    returned_hourly_count=len(raw_hourly["time"]),
                    missing_value_counts=self._missing_value_counts(raw_daily, raw_hourly),
                ),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise OpenMeteoProviderError(
                "Open-Meteo response was missing required metadata or had invalid daily values."
            ) from exc

        self._write_cache(cache_path, weather)
        daily_csv_path, hourly_csv_path = self._write_csv_exports(weather, cache_path)
        return CachedWeather(
            data=weather,
            path=cache_path,
            daily_csv_path=daily_csv_path,
            hourly_csv_path=hourly_csv_path,
            from_cache=False,
        )

    @staticmethod
    def _missing_dates(start_date: date, end_date: date, returned_dates: list[str]) -> list[date]:
        returned = {date.fromisoformat(value) for value in returned_dates}
        expected_count = (end_date - start_date).days + 1
        expected = {
            start_date + timedelta(days=offset)
            for offset in range(expected_count)
        }
        return sorted(expected - returned)

    def _cache_path(self, request: WeatherRequest) -> Path:
        cache_key = json.dumps(
            {
                "endpoint": self.archive_url,
                "location_id": request.location_id,
                "latitude": request.latitude,
                "longitude": request.longitude,
                "start_date": request.start_date.isoformat(),
                "end_date": request.end_date.isoformat(),
                "model": WEATHER_MODEL,
                "daily_variables": DAILY_VARIABLES,
                "hourly_variables": HOURLY_VARIABLES,
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:12]
        safe_location = re.sub(r"[^A-Za-z0-9_-]", "_", request.location_id)
        filename = (
            f"{safe_location}_{request.start_date.isoformat()}_"
            f"{request.end_date.isoformat()}_{digest}.json"
        )
        return self.cache_dir / "raw" / "open_meteo" / filename

    @staticmethod
    def _missing_value_counts(
        daily: dict[str, object],
        hourly: dict[str, object],
    ) -> dict[str, int]:
        missing: dict[str, int] = {}
        for period, series, variable_names in (
            ("daily", daily, DAILY_VARIABLES),
            ("hourly", hourly, HOURLY_VARIABLES),
        ):
            for variable in variable_names:
                values = series.get(variable)
                if not isinstance(values, list):
                    raise ValueError(f"{period} response omitted {variable}")
                missing[f"{period}.{variable}"] = sum(value is None for value in values)
        return missing

    @staticmethod
    def _read_cache(path: Path) -> WeatherResponse:
        try:
            data = WeatherResponse.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, ValidationError) as exc:
            raise WeatherCacheError(
                f"Cached Open-Meteo file {path.name} is unreadable or invalid. "
                "Retry with --force-refresh to reacquire the provider response."
            ) from exc
        return data

    def _write_csv_exports(
        self,
        data: WeatherResponse,
        raw_cache_path: Path,
    ) -> tuple[Path, Path]:
        export_directory = self.cache_dir / "processed" / "open_meteo"
        stem = raw_cache_path.stem
        daily_path = export_directory / f"{stem}_daily.csv"
        hourly_path = export_directory / f"{stem}_hourly.csv"

        daily_rows = (
            (
                day.isoformat(),
                data.location_id,
                data.provenance.requested_latitude,
                data.provenance.requested_longitude,
                data.latitude,
                data.longitude,
                data.provenance.model,
                data.provenance.data_status,
                maximum,
                minimum,
                mean,
                wind_maximum,
            )
            for day, maximum, minimum, mean, wind_maximum in zip(
                data.daily.time,
                data.daily.temperature_2m_max,
                data.daily.temperature_2m_min,
                data.daily.temperature_2m_mean,
                data.daily.wind_speed_10m_max,
                strict=True,
            )
        )
        hourly_rows = (
            (
                timestamp.isoformat(),
                data.location_id,
                data.provenance.requested_latitude,
                data.provenance.requested_longitude,
                data.latitude,
                data.longitude,
                data.provenance.model,
                data.provenance.data_status,
                temperature,
                humidity,
                wind_speed,
            )
            for timestamp, temperature, humidity, wind_speed in zip(
                data.hourly.time,
                data.hourly.temperature_2m,
                data.hourly.relative_humidity_2m,
                data.hourly.wind_speed_10m,
                strict=True,
            )
        )
        self._write_csv(
            daily_path,
            (
                "date_local",
                "location_id",
                "requested_latitude",
                "requested_longitude",
                "resolved_latitude",
                "resolved_longitude",
                "model",
                "data_status",
                "temperature_2m_max_c",
                "temperature_2m_min_c",
                "temperature_2m_mean_c",
                "wind_speed_10m_max_kmh",
            ),
            daily_rows,
        )
        self._write_csv(
            hourly_path,
            (
                "timestamp_local",
                "location_id",
                "requested_latitude",
                "requested_longitude",
                "resolved_latitude",
                "resolved_longitude",
                "model",
                "data_status",
                "temperature_2m_c",
                "relative_humidity_2m_percent",
                "wind_speed_10m_kmh",
            ),
            hourly_rows,
        )
        return daily_path, hourly_path

    @staticmethod
    def _write_csv(
        path: Path,
        header: Sequence[str],
        rows: Iterable[Sequence[object]],
    ) -> None:
        temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary_path.open("w", newline="", encoding="utf-8") as output:
                writer = csv.writer(output)
                writer.writerow(header)
                writer.writerows(rows)
            temporary_path.replace(path)
        except OSError as exc:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                raise WeatherCacheError(
                    f"Could not write CSV export {path.name}, and the temporary "
                    f"file could not be removed: {cleanup_error}"
                ) from exc
            raise WeatherCacheError(
                f"Could not write CSV export {path.name}: {exc}"
            ) from exc

    @staticmethod
    def _write_cache(path: Path, data: WeatherResponse) -> None:
        temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(data.model_dump_json(indent=2), encoding="utf-8")
            temporary_path.replace(path)
        except OSError as exc:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                raise WeatherCacheError(
                    f"Could not write Open-Meteo cache {path.name}, and the "
                    f"temporary file could not be removed: {cleanup_error}"
                ) from exc
            raise WeatherCacheError(
                f"Could not write Open-Meteo cache {path.name}: {exc}"
            ) from exc
