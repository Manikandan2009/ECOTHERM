import json
from pathlib import Path

import pandas as pd
import pytest
from shapely.geometry import box, mapping

import app.services.map_inspection as inspection


def _write_feature_collection(path: Path, features: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )


def _feature(geometry, properties: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": mapping(geometry),
        "properties": properties,
    }


def _write_test_boundaries(cache_dir: Path) -> None:
    district_features = [
        _feature(
            box(80.0, 12.8, 80.5, 13.5),
            {"district_id": "chennai", "district_name": "Chennai"},
        )
    ]
    district_features.extend(
        _feature(
            box(84 + index * 0.01, 12.8, 84.005 + index * 0.01, 13.5),
            {"district_id": f"test_district_{index}", "district_name": f"Test {index}"},
        )
        for index in range(37)
    )
    constituency_features = [
        _feature(
            box(80.1, 12.9, 80.4, 13.3),
            {
                "constituency_id": "ac_021_anna_nagar",
                "constituency_name": "Anna Nagar",
                "district_id": "chennai",
                "district_name": "Chennai",
                "ac_number": 21,
            },
        )
    ]
    constituency_features.extend(
        _feature(
            box(90 + index * 0.01, 12.8, 90.005 + index * 0.01, 13.5),
            {
                "constituency_id": f"ac_{index + 1:03d}_test",
                "constituency_name": f"Test {index}",
                "district_id": "test_district_0",
                "district_name": "Test 0",
                "ac_number": index + 1,
            },
        )
        for index in range(233)
    )
    boundary_dir = cache_dir / "processed" / "boundaries"
    _write_feature_collection(boundary_dir / "districts.geojson", district_features)
    _write_feature_collection(
        boundary_dir / "constituencies.geojson",
        constituency_features,
    )


@pytest.mark.asyncio
async def test_inspection_returns_cached_cell_and_regional_weather(
    tmp_path,
    monkeypatch,
) -> None:
    _write_test_boundaries(tmp_path)
    grid_dir = tmp_path / "processed" / "grids"
    grid_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "grid_id": "chennai-100-00001-00001",
                "centroid_lon": 80.27,
                "centroid_lat": 13.08,
                "lst_c": 42.5,
                "lst_valid_scenes": 7.5,
                "population_estimated_2025": 123.0,
                "season_year": 2026,
            }
        ]
    ).to_csv(grid_dir / "chennai_100m_2026.csv", index=False)
    summary_dir = (
        tmp_path
        / "processed"
        / "constituencies"
        / "static_batches"
        / "ac_021_anna_nagar"
    )
    summary_dir.mkdir(parents=True)
    (summary_dir / "manifest.json").write_text(
        json.dumps({"lst_mean_c": 40.0, "input_resolution_m": 1000}),
        encoding="utf-8",
    )

    async def weather(**kwargs):
        return {
            "temperature_2m_c": 31.0,
            "status": "live",
            "updated_at_utc": "2026-06-15T10:00:00+00:00",
            "error": None,
        }

    monkeypatch.setattr(inspection, "fetch_live_district_weather", weather)
    inspection._load_boundaries.cache_clear()
    inspection._load_city_grid.cache_clear()
    try:
        result = await inspection.inspect_map_point(
            cache_dir=tmp_path,
            latitude=13.08,
            longitude=80.27,
        )
    finally:
        inspection._load_boundaries.cache_clear()
        inspection._load_city_grid.cache_clear()

    assert result.study_area_status == "inside"
    assert result.district_id == "chennai"
    assert result.constituency_id == "ac_021_anna_nagar"
    assert result.cell_resolution_m == 100
    assert result.lst_c.value == 42.5
    assert result.lst_valid_observations.value == 7.5
    assert result.difference_from_constituency_mean_c.value == 2.5
    assert result.population_estimated_2025.value == 123.0
    assert result.air_temperature.temperature_2m_c == 31.0
    assert result.air_temperature.status == "live"
    assert result.cell_outline is not None


@pytest.mark.asyncio
async def test_inspection_uses_statewide_grid_outside_city_grid(
    tmp_path,
    monkeypatch,
) -> None:
    _write_test_boundaries(tmp_path)
    grid_dir = tmp_path / "processed" / "grids"
    grid_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "grid_id": "chennai-100-00099-00099",
                "centroid_lon": 80.45,
                "centroid_lat": 13.45,
                "lst_c": 41.0,
                "lst_valid_scenes": 2,
                "population_estimated_2025": 100.0,
                "season_year": 2026,
            }
        ]
    ).to_csv(grid_dir / "chennai_100m_2026.csv", index=False)
    pd.DataFrame(
        [
            {
                "grid_id": "tamil-nadu-1000-00100-00100",
                "centroid_lon": 80.27,
                "centroid_lat": 13.08,
                "lst_c": 39.5,
                "lst_valid_scenes": 4,
                "ndwi": 0.1,
                "population_estimated_2025": 456.0,
                "season_year": 2026,
            }
        ]
    ).to_csv(grid_dir / "tamil_nadu_1000m_2026.csv", index=False)
    summary_dir = (
        tmp_path
        / "processed"
        / "constituencies"
        / "static_batches"
        / "ac_021_anna_nagar"
    )
    summary_dir.mkdir(parents=True)
    (summary_dir / "manifest.json").write_text(
        json.dumps({"lst_mean_c": 38.0, "input_resolution_m": 1000}),
        encoding="utf-8",
    )

    async def weather(**kwargs):
        return {
            "temperature_2m_c": 31.0,
            "status": "live",
            "updated_at_utc": "2026-06-15T10:00:00+00:00",
            "error": None,
        }

    monkeypatch.setattr(inspection, "fetch_live_district_weather", weather)
    inspection._load_boundaries.cache_clear()
    inspection._load_city_grid.cache_clear()
    try:
        result = await inspection.inspect_map_point(
            cache_dir=tmp_path,
            latitude=13.08,
            longitude=80.27,
        )
    finally:
        inspection._load_boundaries.cache_clear()
        inspection._load_city_grid.cache_clear()

    assert result.study_area_status == "inside"
    assert result.cell_resolution_m == 1000
    assert result.lst_c.value == 39.5
    assert result.difference_from_constituency_mean_c.value == 1.5
    assert result.population_estimated_2025.value == 456.0
    assert result.cell_outline is not None


@pytest.mark.asyncio
async def test_inspection_marks_outside_point_unavailable_without_weather_call(
    tmp_path,
    monkeypatch,
) -> None:
    _write_test_boundaries(tmp_path)

    async def unexpected_weather(**kwargs):
        raise AssertionError("outside points must not trigger a weather lookup")

    monkeypatch.setattr(
        inspection,
        "fetch_live_district_weather",
        unexpected_weather,
    )
    inspection._load_boundaries.cache_clear()
    try:
        result = await inspection.inspect_map_point(
            cache_dir=tmp_path,
            latitude=20.0,
            longitude=80.0,
        )
    finally:
        inspection._load_boundaries.cache_clear()

    assert result.study_area_status == "outside"
    assert result.district_name is None
    assert result.lst_c.status == "unavailable"
    assert "Outside" in (result.lst_c.reason or "")
    assert result.air_temperature.status == "unavailable"


@pytest.mark.asyncio
async def test_inspection_reports_cloud_masked_cell_as_unavailable(
    tmp_path,
    monkeypatch,
) -> None:
    _write_test_boundaries(tmp_path)
    grid_dir = tmp_path / "processed" / "grids"
    grid_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "grid_id": "chennai-100-00001-00001",
                "centroid_lon": 80.27,
                "centroid_lat": 13.08,
                "lst_c": None,
                "lst_valid_scenes": None,
                "population_estimated_2025": None,
                "season_year": 2026,
            }
        ]
    ).to_csv(grid_dir / "chennai_100m_2026.csv", index=False)

    async def weather(**kwargs):
        return {
            "temperature_2m_c": None,
            "status": "unavailable",
            "updated_at_utc": None,
            "error": "No cached forecast value.",
        }

    monkeypatch.setattr(inspection, "fetch_live_district_weather", weather)
    inspection._load_boundaries.cache_clear()
    inspection._load_city_grid.cache_clear()
    try:
        result = await inspection.inspect_map_point(
            cache_dir=tmp_path,
            latitude=13.08,
            longitude=80.27,
        )
    finally:
        inspection._load_boundaries.cache_clear()
        inspection._load_city_grid.cache_clear()

    assert result.lst_c.status == "unavailable"
    assert "cloud-masked" in (result.lst_c.reason or "")
    assert result.population_estimated_2025.status == "unavailable"
    assert result.cell_outline is not None
    assert result.air_temperature.status == "unavailable"
