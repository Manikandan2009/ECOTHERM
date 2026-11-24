import json
from types import SimpleNamespace

import pytest

from app.repositories import analytics


def _write_region_cache(cache_dir, collection, region_id, manifest, rows) -> None:
    directory = (
        cache_dir
        / "processed"
        / collection
        / "static_batches"
        / region_id
    )
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (directory / f"{region_id}_2026.csv").write_text(
        "ndvi,ndvi_valid\n" + rows,
        encoding="utf-8",
    )


def test_environmental_analytics_uses_cached_metrics_and_keeps_weather_context(
    tmp_path,
    monkeypatch,
) -> None:
    _write_region_cache(
        tmp_path,
        "districts",
        "alpha",
        {
            "season_year": 2026,
            "cell_count": 2,
            "lst_valid_cells": 1,
            "lst_mean_c": 40.0,
            "worldpop_population_2025": 1000,
            "lst_composite_start": "2026-04-01",
            "lst_composite_end": "2026-06-30",
        },
        "0.2,True\n0.6,True\ninvalid,True\n",
    )
    _write_region_cache(
        tmp_path,
        "constituencies",
        "ac_001_alpha",
        {
            "season_year": 2026,
            "grid_cell_count": 1,
            "lst_valid_cell_count": 1,
            "lst_mean_c": 42.0,
            "population_estimated_2025": 500,
            "lst_composite_start": "2026-04-01",
            "lst_composite_end": "2026-06-30",
        },
        "0.4,True\n",
    )
    monkeypatch.setattr(
        analytics,
        "load_district_boundaries",
        lambda _: {"districts": [{"district_id": "alpha", "district_name": "Alpha"}]},
    )
    monkeypatch.setattr(
        analytics,
        "load_constituencies",
        lambda _: {
            "constituencies": [{
                "constituency_id": "ac_001_alpha",
                "constituency_name": "Alpha Seat",
                "district_id": "alpha",
                "district_name": "Alpha",
            }]
        },
    )
    monkeypatch.setattr(
        analytics,
        "load_dashboard_summary",
        lambda *args, **kwargs: SimpleNamespace(
            weather_mean_air_temperature_c=30.0,
            weather_model="era5_land",
            weather_start_date="2026-04-01",
            weather_end_date="2026-06-30",
        ),
    )

    result = analytics.load_environmental_analytics(tmp_path, season_year=2026)

    district, constituency = result.regions
    assert result.data_status == "available"
    assert district.lst_mean_c == 40
    assert district.lst_coverage_percent == 50
    assert district.ndvi_mean == pytest.approx(0.4)
    assert district.air_temperature_mean_c == 30
    assert constituency.population_estimated_2025 == 500
    assert constituency.air_temperature_mean_c == 30.0
    assert constituency.air_temperature_model == "era5_land"
    assert constituency.air_temperature_start_date == "2026-04-01"
    assert constituency.air_temperature_end_date == "2026-06-30"
    assert "district reference point" in constituency.air_temperature_reason
    assert "not a constituency-specific measurement" in constituency.air_temperature_reason
    assert "0.1° (~11 km)" in result.air_temperature_source


def test_environmental_analytics_keeps_missing_cache_values_unavailable(tmp_path) -> None:
    result = analytics._load_region(
        tmp_path,
        season_year=2026,
        region_id="missing",
        region_name="Missing",
        district_id="missing",
        district_name="Missing",
        region_type="district",
    )

    assert result.data_status == "unavailable"
    assert result.lst_mean_c is None
    assert "No cached 2026 district data" in result.lst_reason
    assert result.resolution_m is None
    assert result.composite_start is None
