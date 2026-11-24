import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import transform as transform_geometry
from pyproj import Transformer
from shapely.geometry import Point, box

from app.schemas.inspection import (
    InspectMetric,
    MapInspectionResponse,
    RegionalAirTemperature,
)
from app.services.live_weather import LiveWeatherError, fetch_live_district_weather


CITY_GRID_FILES = {
    "chennai": "chennai_100m_2026.csv",
    "coimbatore": "coimbatore_100m_2026.csv",
    "madurai": "madurai_100m_2026.csv",
}
GRID_CRS = "EPSG:32644"
CITY_GRID_RESOLUTION_M = 100
STATE_GRID_RESOLUTION_M = 1000


class MapInspectionError(RuntimeError):
    """Raised when required cached boundaries cannot be read safely."""


@lru_cache(maxsize=1)
def _load_boundaries(cache_dir: str) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    boundary_dir = Path(cache_dir) / "processed" / "boundaries"
    try:
        district_payload = json.loads(
            (boundary_dir / "districts.geojson").read_text(encoding="utf-8")
        )
        constituency_payload = json.loads(
            (boundary_dir / "constituencies.geojson").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise MapInspectionError(f"Could not read cached boundaries: {exc}") from exc

    if not isinstance(district_payload, dict) or not isinstance(
        constituency_payload,
        dict,
    ):
        raise MapInspectionError("Cached boundary files must contain GeoJSON objects.")
    district_features = district_payload.get("features")
    constituency_features = constituency_payload.get("features")
    if not isinstance(district_features, list) or len(district_features) != 38:
        raise MapInspectionError("Expected 38 cached Tamil Nadu district boundaries.")
    if not isinstance(constituency_features, list) or len(constituency_features) != 234:
        raise MapInspectionError("Expected 234 cached Tamil Nadu constituency boundaries.")

    try:
        districts = gpd.GeoDataFrame.from_features(
            district_features,
            crs="EPSG:4326",
        )
        constituencies = gpd.GeoDataFrame.from_features(
            constituency_features,
            crs="EPSG:4326",
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MapInspectionError(f"Cached boundary geometry is invalid: {exc}") from exc
    return districts, constituencies


@lru_cache(maxsize=4)
def _load_city_grid(csv_path: str) -> pd.DataFrame:
    required = {
        "grid_id",
        "centroid_lon",
        "centroid_lat",
        "lst_c",
        "lst_valid_scenes",
        "population_estimated_2025",
        "season_year",
    }
    try:
        grid = pd.read_csv(csv_path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise MapInspectionError(f"Could not read cached city grid: {exc}") from exc
    missing = required - set(grid.columns)
    if missing:
        raise MapInspectionError(
            "Cached city grid is missing required columns: "
            + ", ".join(sorted(missing))
        )
    if grid.empty:
        return grid

    transformer = Transformer.from_crs(
        "EPSG:4326",
        GRID_CRS,
        always_xy=True,
    )
    x_values, y_values = transformer.transform(
        grid["centroid_lon"].to_numpy(dtype=float),
        grid["centroid_lat"].to_numpy(dtype=float),
    )
    grid["_x"] = x_values
    grid["_y"] = y_values
    return grid


def _finite_number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _unavailable(reason: str) -> InspectMetric:
    return InspectMetric(value=None, status="unavailable", reason=reason)


def _find_cell(
    grid: pd.DataFrame,
    *,
    longitude: float,
    latitude: float,
    resolution_m: int,
) -> tuple[pd.Series | None, Any | None]:
    if grid.empty:
        return None, None
    transformer = Transformer.from_crs(
        "EPSG:4326",
        GRID_CRS,
        always_xy=True,
    )
    x, y = transformer.transform(longitude, latitude)
    dx = grid["_x"].to_numpy(dtype=float) - x
    dy = grid["_y"].to_numpy(dtype=float) - y
    distances = dx * dx + dy * dy
    index = int(np.argmin(distances))
    half_size = resolution_m / 2
    if abs(dx[index]) > half_size or abs(dy[index]) > half_size:
        return None, None

    row = grid.iloc[index]
    cell_projected = box(
        float(row["_x"]) - half_size,
        float(row["_y"]) - half_size,
        float(row["_x"]) + half_size,
        float(row["_y"]) + half_size,
    )
    to_geographic = Transformer.from_crs(
        GRID_CRS,
        "EPSG:4326",
        always_xy=True,
    )
    return row, transform_geometry(
        cell_projected,
        to_geographic.transform,
        interleaved=False,
    )


async def inspect_map_point(
    *,
    cache_dir: Path,
    latitude: float,
    longitude: float,
    timeout_seconds: float = 30,
) -> MapInspectionResponse:
    districts, constituencies = _load_boundaries(str(cache_dir.resolve()))
    point = Point(longitude, latitude)
    district_matches = districts[districts.geometry.covers(point)]
    if district_matches.empty:
        outside = "Outside the cached Tamil Nadu district study area."
        unavailable = _unavailable(outside)
        return MapInspectionResponse(
            latitude=latitude,
            longitude=longitude,
            study_area_status="outside",
            lst_c=unavailable,
            lst_valid_observations=unavailable,
            constituency_mean_lst_c=unavailable,
            difference_from_constituency_mean_c=unavailable,
            population_estimated_2025=unavailable,
            air_temperature=RegionalAirTemperature(
                temperature_2m_c=None,
                status="unavailable",
                updated_at_utc=None,
                reason=outside,
            ),
        )

    district_matches = district_matches.sort_values("district_id", kind="stable")
    district = district_matches.iloc[0]
    district_id = str(district["district_id"])
    district_name = str(district["district_name"])

    constituency_matches = constituencies[constituencies.geometry.covers(point)]
    constituency_id: str | None = None
    constituency_name: str | None = None
    if not constituency_matches.empty:
        constituency_matches = constituency_matches.sort_values(
            "ac_number",
            kind="stable",
        )
        constituency = constituency_matches.iloc[0]
        constituency_id = str(constituency["constituency_id"])
        constituency_name = str(constituency["constituency_name"])

    cell = None
    cell_outline = None
    cell_id = None
    cell_resolution_m = None
    lst_metric = _unavailable("No cached 100 m or 1 km cell covers this point.")
    observation_metric = _unavailable(
        "No cached 100 m or 1 km cell covers this point."
    )
    population_metric = _unavailable(
        "No cached 100 m or 1 km cell covers this point."
    )
    composite_start = None
    composite_end = None
    season_year = 2026

    grid_filename = CITY_GRID_FILES.get(district_id)
    if grid_filename:
        grid_path = cache_dir / "processed" / "grids" / grid_filename
        if grid_path.is_file():
            grid = _load_city_grid(str(grid_path.resolve()))
            cell, cell_outline = _find_cell(
                grid,
                longitude=longitude,
                latitude=latitude,
                resolution_m=CITY_GRID_RESOLUTION_M,
            )
            if cell is not None:
                cell_resolution_m = CITY_GRID_RESOLUTION_M

    if cell is None:
        state_grid_path = (
            cache_dir
            / "processed"
            / "grids"
            / f"tamil_nadu_{STATE_GRID_RESOLUTION_M}m_{season_year}.csv"
        )
        if state_grid_path.is_file():
            state_grid = _load_city_grid(str(state_grid_path.resolve()))
            cell, cell_outline = _find_cell(
                state_grid,
                longitude=longitude,
                latitude=latitude,
                resolution_m=STATE_GRID_RESOLUTION_M,
            )
            if cell is not None:
                cell_resolution_m = STATE_GRID_RESOLUTION_M

    if cell is not None:
        cell_id = str(cell["grid_id"])
        season_year = int(cell["season_year"])
        composite_start = f"{season_year}-04-01"
        composite_end = f"{season_year}-06-30"
        lst_value = _finite_number(cell["lst_c"])
        valid_observations = _finite_number(cell["lst_valid_scenes"])
        population_value = _finite_number(cell["population_estimated_2025"])
        lst_missing_reason = "cloud-masked cell: no valid Landsat observation in the composite."
        lst_metric = (
            InspectMetric(value=lst_value, status="available")
            if lst_value is not None
            else _unavailable(lst_missing_reason)
        )
        observation_metric = (
            InspectMetric(value=valid_observations, status="available")
            if valid_observations is not None
            else _unavailable(lst_missing_reason)
        )
        population_metric = (
            InspectMetric(value=population_value, status="available")
            if population_value is not None
            else _unavailable(
                "WorldPop has no valid estimated population value for this cell."
            )
        )

    constituency_mean = None
    constituency_mean_metric = _unavailable(
        "No cached constituency LST mean is available for this point."
    )
    difference_metric = _unavailable(
        "A cell LST and constituency mean are both required to calculate this difference."
    )
    constituency_mean_resolution = None
    if constituency_id:
        manifest_path = (
            cache_dir
            / "processed"
            / "constituencies"
            / "static_batches"
            / constituency_id
            / "manifest.json"
        )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            manifest = None
        except (OSError, json.JSONDecodeError) as exc:
            raise MapInspectionError(
                f"Could not read cached constituency summary: {exc}"
            ) from exc
        if manifest is not None and not isinstance(manifest, dict):
            raise MapInspectionError(
                "Cached constituency summary must contain a JSON object."
            )
        if manifest:
            constituency_mean = _finite_number(manifest.get("lst_mean_c"))
            if constituency_mean is not None:
                constituency_mean_metric = InspectMetric(
                    value=constituency_mean,
                    status="available",
                )
                constituency_mean_resolution = int(
                    manifest.get("input_resolution_m", 1000)
                )
                cell_lst = lst_metric.value
                if lst_metric.status == "available" and cell_lst is not None:
                    difference_metric = InspectMetric(
                        value=cell_lst - constituency_mean,
                        status="available",
                    )
            else:
                constituency_mean_metric = _unavailable(
                    "The cached constituency summary has no finite LST mean."
                )

    try:
        weather_payload = await fetch_live_district_weather(
            cache_dir=cache_dir,
            district_id=district_id,
            timeout_seconds=timeout_seconds,
        )
        temperature = _finite_number(weather_payload.get("temperature_2m_c"))
        weather = RegionalAirTemperature(
            temperature_2m_c=temperature,
            status=(
                weather_payload.get("status", "unavailable")
                if temperature is not None
                else "unavailable"
            ),
            updated_at_utc=(
                weather_payload.get("updated_at_utc")
                if temperature is not None
                else None
            ),
            reason=weather_payload.get("error"),
        )
        if temperature is None and not weather.reason:
            weather.reason = "Open-Meteo returned no current temperature value."
    except LiveWeatherError as exc:
        weather = RegionalAirTemperature(
            temperature_2m_c=None,
            status="unavailable",
            updated_at_utc=None,
            reason=str(exc),
        )

    return MapInspectionResponse(
        latitude=latitude,
        longitude=longitude,
        study_area_status="inside",
        district_id=district_id,
        district_name=district_name,
        constituency_id=constituency_id,
        constituency_name=constituency_name,
        cell_id=cell_id,
        cell_resolution_m=cell_resolution_m,
        cell_outline=(
            dict(cell_outline.__geo_interface__)
            if cell_outline is not None
            else None
        ),
        lst_c=lst_metric,
        lst_composite_start=composite_start,
        lst_composite_end=composite_end,
        lst_valid_observations=observation_metric,
        lst_observation_count_note=(
            "Spatial mean of per-pixel valid Landsat scene counts within this grid cell."
            if observation_metric.status == "available"
            else None
        ),
        constituency_mean_lst_c=constituency_mean_metric,
        constituency_mean_resolution_m=constituency_mean_resolution,
        difference_from_constituency_mean_c=difference_metric,
        population_estimated_2025=population_metric,
        air_temperature=weather,
    )
