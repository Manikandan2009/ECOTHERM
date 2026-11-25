import json

import pytest

from app.repositories import analytics
from app.schemas.analytics import AnalyticsResponse


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
        "load_cached_weather_summary",
        lambda *args, **kwargs: (
            30.0,
            None,
            "era5_land",
            "reanalysis_estimate",
            "2026-04-01",
            "2026-06-30",
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


def test_environmental_analytics_cache_reuses_results_and_invalidates_on_file_change(
    tmp_path,
    monkeypatch,
) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()
    dataset = processed / "ecotherm.sqlite"
    dataset.write_bytes(b"v1")
    calls = []

    def build_result(cache_dir, *, season_year):
        calls.append((cache_dir, season_year))
        return AnalyticsResponse(
            season_year=season_year,
            data_status="unavailable",
            lst_source="test",
            population_source="test",
            ndvi_source="test",
            air_temperature_source="test",
            regions=[],
        )

    analytics.clear_environmental_analytics_cache()
    monkeypatch.setattr(
        analytics,
        "_load_environmental_analytics_uncached",
        build_result,
    )

    first = analytics.load_environmental_analytics(tmp_path, season_year=2026)
    first.lst_source = "caller mutation"
    second = analytics.load_environmental_analytics(tmp_path, season_year=2026)
    assert first is not second
    assert second.lst_source == "test"
    assert len(calls) == 1

    dataset.write_bytes(b"v2 with a changed size")
    analytics.load_environmental_analytics(tmp_path, season_year=2026)
    assert len(calls) == 2
    analytics.clear_environmental_analytics_cache()
