import csv

from app.repositories import weather_cache


def _write_weather(path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "date_local",
                "location_id",
                "model",
                "data_status",
                "temperature_2m_max_c",
                "temperature_2m_mean_c",
            ]
        )
        writer.writerow(
            ["2026-04-01", "district_a_reference", "era5_land",
             "reanalysis_estimate", "36.0", value]
        )
        writer.writerow(
            ["2026-04-02", "district_b_reference", "era5_land",
             "reanalysis_estimate", "38.0", "32.0"]
        )


def test_weather_summaries_share_parsing_and_invalidate_when_source_changes(
    tmp_path,
    monkeypatch,
) -> None:
    weather_cache.clear_weather_summary_cache()
    path = tmp_path / "processed" / "open_meteo" / "daily_daily.csv"
    _write_weather(path, "30.0")
    reader_count = 0
    original_reader = csv.DictReader

    def counting_reader(*args, **kwargs):
        nonlocal reader_count
        reader_count += 1
        return original_reader(*args, **kwargs)

    monkeypatch.setattr(weather_cache.csv, "DictReader", counting_reader)

    first = weather_cache.load_cached_weather_summary(
        tmp_path,
        location_id="district_a_reference",
        season_year=2026,
    )
    second = weather_cache.load_cached_weather_summary(
        tmp_path,
        location_id="district_b_reference",
        season_year=2026,
    )
    assert first == (
        30.0,
        36.0,
        "era5_land",
        "reanalysis_estimate",
        "2026-04-01",
        "2026-04-01",
    )
    assert second[0] == 32.0
    assert second[1] == 38.0
    assert reader_count == 1

    _write_weather(path, "31.000")
    updated = weather_cache.load_cached_weather_summary(
        tmp_path,
        location_id="district_a_reference",
        season_year=2026,
    )
    assert updated[0] == 31.0
    assert reader_count == 2
    weather_cache.clear_weather_summary_cache()
