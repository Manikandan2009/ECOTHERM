import pandas as pd

from app.services.constituency_aggregates import _summarize_constituency


def test_constituency_with_no_high_risk_cells_has_zero_exposed_population():
    cells = pd.DataFrame(
        {
            "lst_c": [20.0, 21.0],
            "ndvi": [0.8, 0.9],
            "ndbi": [-0.5, -0.4],
            "population_estimated_2025": [10.0, 20.0],
        }
    )

    summary = _summarize_constituency(cells)

    assert summary["high_risk_cell_count"] == 0
    assert summary["people_exposed_high_heat"] == 0.0
    assert summary["risk_score_mean"] is not None
