import pytest

from app.repositories import priorities
from app.schemas.analytics import AnalyticsRegion, AnalyticsResponse


def _constituency(region_id, lst, population, ndvi):
    return AnalyticsRegion(
        region_id=region_id,
        region_name=region_id,
        region_type="constituency",
        district_id="district",
        district_name="District",
        data_status="available" if lst is not None else "partial",
        cell_count=10,
        lst_mean_c=lst,
        lst_coverage_percent=100,
        population_estimated_2025=population,
        ndvi_mean=ndvi,
        resolution_m=1000,
        composite_start="2026-04-01",
        composite_end="2026-06-30",
        lst_reason=None if lst is not None else "No valid LST cells.",
        population_reason=None if population is not None else "No population cache.",
        ndvi_reason=None if ndvi is not None else "No valid NDVI cells.",
        air_temperature_mean_c=None,
        air_temperature_model=None,
        air_temperature_start_date=None,
        air_temperature_end_date=None,
        air_temperature_reason="District-only context.",
    )


def test_priority_formula_uses_percentile_population_and_low_green_proxy(
    tmp_path,
    monkeypatch,
) -> None:
    rows = [
        _constituency("cool-small-green", 30, 100, 0.8),
        _constituency("warm-medium", 40, 200, 0.2),
        _constituency("hottest-large-low-green", 50, 400, -0.2),
    ]
    monkeypatch.setattr(
        priorities,
        "load_environmental_analytics",
        lambda *args, **kwargs: AnalyticsResponse(
            season_year=2026,
            data_status="available",
            lst_source="Landsat",
            population_source="WorldPop",
            ndvi_source="Sentinel-2",
            air_temperature_source="Open-Meteo",
            regions=rows,
        ),
    )

    result = priorities.load_constituency_priorities(tmp_path, season_year=2026)

    hottest = result.priorities[0]
    assert hottest.constituency_id == "hottest-large-low-green"
    assert hottest.heat_exposure_percentile == pytest.approx(1)
    assert hottest.population_weight == pytest.approx(1)
    assert hottest.low_green_score == pytest.approx(0.6)
    assert hottest.priority_score == pytest.approx(60)
    assert result.formula.startswith("score (0–100)")


def test_priority_is_unavailable_when_any_required_input_is_missing(
    tmp_path,
    monkeypatch,
) -> None:
    missing = _constituency("missing-ndvi", 42, 500, None)
    monkeypatch.setattr(
        priorities,
        "load_environmental_analytics",
        lambda *args, **kwargs: AnalyticsResponse(
            season_year=2026,
            data_status="partial",
            lst_source="Landsat",
            population_source="WorldPop",
            ndvi_source="Sentinel-2",
            air_temperature_source="Open-Meteo",
            regions=[missing],
        ),
    )

    result = priorities.load_constituency_priorities(tmp_path, season_year=2026)

    assert result.priorities[0].priority_score is None
    assert "No valid NDVI cells" in result.priorities[0].priority_reason
