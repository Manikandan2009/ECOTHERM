import sqlite3
from pathlib import Path

from app.schemas.predictions import PredictionStatus


class PredictionRepositoryError(RuntimeError):
    """Raised when prediction readiness data cannot be read."""


def load_prediction_status(
    database_path: Path,
    *,
    region_id: str,
) -> PredictionStatus:
    if not database_path.is_file():
        return _unavailable_status(region_id, [], [])

    try:
        database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(database_uri, uri=True) as connection:
            has_grid_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='grid_observations'"
            ).fetchone()
            if not has_grid_table:
                return _unavailable_status(region_id, [], [])
            available_seasons = [
                int(row[0])
                for row in connection.execute(
                    "SELECT DISTINCT season_year FROM grid_observations ORDER BY season_year"
                )
            ]
            region_rows = connection.execute(
                """
                SELECT season_year, COUNT(*),
                       SUM(CASE WHEN lst_c IS NOT NULL THEN 1 ELSE 0 END)
                FROM grid_observations
                WHERE region_id = ?
                GROUP BY season_year
                ORDER BY season_year
                """,
                (region_id,),
            ).fetchall()
    except sqlite3.Error as exc:
        raise PredictionRepositoryError(
            f"Could not read prediction readiness data: {exc}"
        ) from exc

    region_seasons = [int(row[0]) for row in region_rows]
    latest_region = region_rows[-1] if region_rows else None
    return _unavailable_status(
        region_id,
        available_seasons,
        region_seasons,
        latest_region_cell_count=int(latest_region[1]) if latest_region else None,
        latest_region_lst_valid_cell_count=(
            int(latest_region[2] or 0) if latest_region else None
        ),
    )


def _unavailable_status(
    region_id: str,
    available_seasons: list[int],
    region_seasons: list[int],
    *,
    latest_region_cell_count: int | None = None,
    latest_region_lst_valid_cell_count: int | None = None,
) -> PredictionStatus:
    if not available_seasons:
        reason = (
            "No cached analysis seasons are available to construct or evaluate "
            "a prediction model."
        )
    elif len(available_seasons) == 1:
        reason = (
            f"Only the {available_seasons[0]} summer season is cached. A separate "
            "season is required for temporal holdout evaluation; no qualified "
            "model or measured spatial/temporal validation is available."
        )
    else:
        reason = (
            "Cached seasons exist, but no qualified model with a fixed target, "
            "evaluated baseline, and measured spatial and temporal holdout results "
            "is registered."
        )
    return PredictionStatus(
        region_id=region_id,
        status="unavailable",
        model_status="no_qualified_model",
        prediction_available=False,
        available_season_years=available_seasons,
        region_season_years=region_seasons,
        latest_region_cell_count=latest_region_cell_count,
        latest_region_lst_valid_cell_count=latest_region_lst_valid_cell_count,
        target_status="not_defined",
        baseline_status="not_evaluated",
        spatial_validation_status="not_run",
        temporal_validation_status="not_run",
        reason=reason,
    )
