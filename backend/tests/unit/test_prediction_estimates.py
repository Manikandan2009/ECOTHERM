import csv

import pytest

from app.repositories.prediction_estimates import load_prediction_estimate


def _write_training_grid(cache_dir) -> None:
    fieldnames = (
        "lst_c",
        "ndvi",
        "ndbi",
        "district_id",
        "lst_valid",
        "ndvi_valid",
        "ndbi_valid",
    )
    rows = []
    for district_number in range(8):
        for cell_number in range(10):
            ndvi = 0.1 + district_number * 0.025 + cell_number * 0.01
            ndbi = -0.4 + district_number * 0.02 + cell_number * 0.015
            rows.append({
                "lst_c": 32 + 6 * ndvi - 4 * ndbi,
                "ndvi": ndvi,
                "ndbi": ndbi,
                "district_id": f"district_{district_number}",
                "lst_valid": "True",
                "ndvi_valid": "True",
                "ndbi_valid": "True",
            })

    grid_dir = cache_dir / "processed" / "grids"
    grid_dir.mkdir(parents=True)
    with (grid_dir / "tamil_nadu_1000m_2026.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    district_root = cache_dir / "processed" / "districts" / "static_batches"
    for district_number in range(8):
        district_id = f"district_{district_number}"
        directory = district_root / district_id
        directory.mkdir(parents=True)
        with (directory / f"{district_id}_2026.csv").open(
            "w",
            encoding="utf-8",
            newline="",
        ) as destination:
            writer = csv.DictWriter(destination, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(
                row for row in rows if row["district_id"] == district_id
            )


def test_spatial_estimate_holds_out_complete_districts_and_reports_metrics(
    tmp_path,
) -> None:
    _write_training_grid(tmp_path)

    estimate = load_prediction_estimate(
        tmp_path,
        region_id="tamil_nadu",
        season_year=2026,
    )

    assert estimate.model_status == "available"
    assert estimate.output_label == "estimate"
    assert estimate.forecast_label == "not_a_forecast"
    assert estimate.training_cell_count + estimate.test_cell_count == 80
    assert set(estimate.training_districts).isdisjoint(estimate.test_districts)
    assert estimate.r_squared == pytest.approx(1.0)
    assert estimate.mean_absolute_error_c == pytest.approx(0.0, abs=1e-10)
    assert estimate.scenario_baseline_lst_c is not None
    assert sum(
        feature.relative_importance_percent
        for feature in estimate.feature_importance
    ) == pytest.approx(100)
    assert "not literal built-up share" in estimate.inputs[1].source
