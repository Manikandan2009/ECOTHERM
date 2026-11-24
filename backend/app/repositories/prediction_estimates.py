import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.prediction_estimate import (
    PredictionEstimate,
    PredictionFeatureImportance,
    PredictionInput,
)

NDVI_SOURCE = "Sentinel-2 SR Harmonized NDVI seasonal median"
NDBI_SOURCE = "Sentinel-2 SR Harmonized NDBI built-up index proxy; not literal built-up share"
LST_SOURCE = "Landsat 8/9 Collection 2 Level 2 L2SP ST_B10 seasonal median"
MODEL_NAME = "Standardized linear regression"
VALIDATION_METHOD = "GroupShuffleSplit by district; 25% of districts held out; random_state=42"


class PredictionEstimateRepositoryError(RuntimeError):
    """Raised when cached model inputs cannot be read."""


def load_prediction_estimate(
    cache_dir: Path,
    *,
    region_id: str,
    season_year: int,
) -> PredictionEstimate:
    model = _fit_cached_model(str(cache_dir.resolve()), season_year)
    if model["status"] != "available":
        return _unavailable_estimate(
            region_id,
            season_year,
            model["reason"],
            training_cell_count=model["training_cell_count"],
            test_cell_count=model["test_cell_count"],
            training_districts=model["training_districts"],
            test_districts=model["test_districts"],
        )

    ndvi_mean, ndbi_mean, scenario_reason = _load_region_features(
        cache_dir,
        region_id=region_id,
        season_year=season_year,
    )
    start_date = f"{season_year}-04-01"
    end_date = f"{season_year}-06-30"
    inputs = [
        PredictionInput(
            feature="ndvi",
            label="Vegetation greenness (NDVI)",
            value=ndvi_mean,
            source=NDVI_SOURCE,
            resolution_m=1000 if ndvi_mean is not None else None,
            composite_start=start_date if ndvi_mean is not None else None,
            composite_end=end_date if ndvi_mean is not None else None,
            reason=None if ndvi_mean is not None else scenario_reason,
        ),
        PredictionInput(
            feature="ndbi",
            label="Built-up index (NDBI proxy)",
            value=ndbi_mean,
            source=NDBI_SOURCE,
            resolution_m=1000 if ndbi_mean is not None else None,
            composite_start=start_date if ndbi_mean is not None else None,
            composite_end=end_date if ndbi_mean is not None else None,
            reason=None if ndbi_mean is not None else scenario_reason,
        ),
    ]
    scenario_available = ndvi_mean is not None and ndbi_mean is not None
    baseline_prediction = (
        model["intercept"]
        + model["ndvi_coefficient"] * ndvi_mean
        + model["ndbi_coefficient"] * ndbi_mean
        if scenario_available
        else None
    )
    return PredictionEstimate(
        region_id=region_id,
        season_year=season_year,
        model_status="available",
        model_name=MODEL_NAME,
        target="Cached cell-level Landsat LST in °C; spatial estimation, not future heat",
        target_source=LST_SOURCE,
        validation_method=VALIDATION_METHOD,
        training_districts=model["training_districts"],
        test_districts=model["test_districts"],
        training_cell_count=model["training_cell_count"],
        test_cell_count=model["test_cell_count"],
        training_district_count=len(model["training_districts"]),
        test_district_count=len(model["test_districts"]),
        r_squared=model["r_squared"],
        mean_absolute_error_c=model["mean_absolute_error_c"],
        p90_absolute_error_c=model["p90_absolute_error_c"],
        evaluation_resolution_m=1000,
        evaluation_start_date=start_date,
        evaluation_end_date=end_date,
        inputs=inputs,
        feature_importance=model["feature_importance"],
        model_intercept_c=model["intercept"],
        ndvi_coefficient_c_per_index=model["ndvi_coefficient"],
        ndbi_coefficient_c_per_index=model["ndbi_coefficient"],
        scenario_ndvi_mean=ndvi_mean,
        scenario_ndbi_mean=ndbi_mean,
        scenario_baseline_lst_c=baseline_prediction,
        scenario_error_bound_c=model["p90_absolute_error_c"],
        scenario_reason=None if scenario_available else scenario_reason,
        reason=None,
    )


@lru_cache(maxsize=4)
def _fit_cached_model(cache_dir_value: str, season_year: int) -> dict[str, Any]:
    cache_dir = Path(cache_dir_value)
    district_cache_dir = (
        cache_dir / "processed" / "districts" / "static_batches"
    )
    try:
        district_files = [
            directory / f"{directory.name}_{season_year}.csv"
            for directory in sorted(district_cache_dir.iterdir())
            if directory.is_dir()
            and (directory / f"{directory.name}_{season_year}.csv").is_file()
        ] if district_cache_dir.is_dir() else []
    except OSError as exc:
        raise PredictionEstimateRepositoryError(
            f"Could not list cached district grids: {exc}"
        ) from exc
    if not district_files:
        return _unavailable_model(
            f"No cached district grids are available for spatial model training in {season_year}."
        )

    try:
        import numpy as np
        import pandas as pd
        from sklearn.linear_model import LinearRegression
        from sklearn.model_selection import GroupShuffleSplit
        from sklearn.preprocessing import StandardScaler

        district_frames = []
        for district_file in district_files:
            frame = pd.read_csv(
                district_file,
                usecols=lambda column: column in {
                    "lst_c",
                    "ndvi",
                    "ndbi",
                    "lst_valid",
                    "ndvi_valid",
                    "ndbi_valid",
                },
            )
            required = {"lst_c", "ndvi", "ndbi"}
            if not required.issubset(frame.columns):
                raise ValueError(
                    f"{district_file.name} is missing: "
                    f"{', '.join(sorted(required - set(frame.columns)))}"
                )
            frame["district_id"] = district_file.parent.name
            district_frames.append(frame)
        data = pd.concat(district_frames, ignore_index=True)
    except ImportError as exc:
        raise PredictionEstimateRepositoryError(
            "The spatial estimate requires the backend ML dependencies, including scikit-learn."
        ) from exc
    except ValueError as exc:
        raise PredictionEstimateRepositoryError(
            f"Cached district grid is missing a required model input: {exc}"
        ) from exc
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise PredictionEstimateRepositoryError(
            f"Could not read the cached district model inputs: {exc}"
        ) from exc

    if "lst_valid" in data:
        data = data[data["lst_valid"].astype(str).str.casefold().eq("true")]
    if "ndvi_valid" in data:
        data = data[data["ndvi_valid"].astype(str).str.casefold().eq("true")]
    if "ndbi_valid" in data:
        data = data[data["ndbi_valid"].astype(str).str.casefold().eq("true")]
    data = data.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["lst_c", "ndvi", "ndbi", "district_id"]
    )
    data = data[
        data["lst_c"].between(0, 80)
        & data["ndvi"].between(-1, 1)
        & data["ndbi"].between(-1, 1)
        & data["district_id"].astype(str).str.strip().ne("")
    ]
    districts = sorted(data["district_id"].astype(str).unique())
    if len(data) < 20 or len(districts) < 4:
        return _unavailable_model(
            "At least 20 paired cells across four districts are required for a spatial holdout."
        )

    x_values = data[["ndvi", "ndbi"]].to_numpy(dtype=float)
    y_values = data["lst_c"].to_numpy(dtype=float)
    groups = data["district_id"].astype(str).to_numpy()
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_indexes, test_indexes = next(splitter.split(x_values, y_values, groups))
    train_districts = sorted(set(groups[train_indexes]))
    test_districts = sorted(set(groups[test_indexes]))
    if not train_districts or not test_districts:
        return _unavailable_model(
            "The spatial split did not produce both training and test districts."
        )

    scaler = StandardScaler()
    x_train = scaler.fit_transform(x_values[train_indexes])
    estimator = LinearRegression()
    estimator.fit(x_train, y_values[train_indexes])
    predictions = estimator.predict(scaler.transform(x_values[test_indexes]))
    residuals = predictions - y_values[test_indexes]
    absolute_errors = np.abs(residuals)
    ss_total = float(np.sum((y_values[test_indexes] - np.mean(y_values[test_indexes])) ** 2))
    ss_residual = float(np.sum(residuals ** 2))
    r_squared = (
        1 - ss_residual / ss_total
        if ss_total > 0
        else None
    )
    mean_absolute_error = float(np.mean(absolute_errors))
    p90_absolute_error = float(np.quantile(absolute_errors, 0.9))
    standardized_coefficients = estimator.coef_.astype(float)
    raw_coefficients = standardized_coefficients / scaler.scale_
    intercept = float(estimator.intercept_ - np.dot(raw_coefficients, scaler.mean_))
    total_importance = float(np.sum(np.abs(standardized_coefficients)))
    feature_names = ("ndvi", "ndbi")
    feature_labels = {
        "ndvi": "Vegetation greenness (NDVI)",
        "ndbi": "Built-up index (NDBI proxy)",
    }
    feature_sources = {"ndvi": NDVI_SOURCE, "ndbi": NDBI_SOURCE}
    importance = [
        PredictionFeatureImportance(
            feature=name,
            label=feature_labels[name],
            standardized_coefficient=float(standardized_coefficients[index]),
            relative_importance_percent=(
                float(abs(standardized_coefficients[index]) / total_importance * 100)
                if total_importance > 0
                else 0.0
            ),
            source=feature_sources[name],
            resolution_m=1000,
        )
        for index, name in enumerate(feature_names)
    ]
    return {
        "status": "available",
        "reason": None,
        "training_districts": train_districts,
        "test_districts": test_districts,
        "training_cell_count": int(len(train_indexes)),
        "test_cell_count": int(len(test_indexes)),
        "r_squared": float(r_squared) if r_squared is not None and math.isfinite(r_squared) else None,
        "mean_absolute_error_c": mean_absolute_error,
        "p90_absolute_error_c": p90_absolute_error,
        "feature_importance": importance,
        "intercept": intercept,
        "ndvi_coefficient": float(raw_coefficients[0]),
        "ndbi_coefficient": float(raw_coefficients[1]),
    }


def _load_region_features(
    cache_dir: Path,
    *,
    region_id: str,
    season_year: int,
) -> tuple[float | None, float | None, str | None]:
    if region_id == "tamil_nadu":
        csv_path = (
            cache_dir
            / "processed"
            / "grids"
            / f"tamil_nadu_1000m_{season_year}.csv"
        )
    elif region_id.startswith("district_"):
        district_id = region_id.removeprefix("district_")
        csv_path = (
            cache_dir
            / "processed"
            / "districts"
            / "static_batches"
            / district_id
            / f"{district_id}_{season_year}.csv"
        )
    elif region_id.startswith("constituency_"):
        constituency_id = region_id.removeprefix("constituency_")
        csv_path = (
            cache_dir
            / "processed"
            / "constituencies"
            / "static_batches"
            / constituency_id
            / f"{constituency_id}_{season_year}.csv"
        )
    else:
        return None, None, f"Region {region_id} has no supported cached grid."
    if not csv_path.is_file():
        return None, None, f"No cached model-input grid is available for {region_id}."

    try:
        import numpy as np
        import pandas as pd

        data = pd.read_csv(
            csv_path,
            usecols=lambda column: column in {
                "ndvi",
                "ndbi",
                "ndvi_valid",
                "ndbi_valid",
            },
        )
        required = {"ndvi", "ndbi"}
        if not required.issubset(data.columns):
            raise ValueError(
                f"missing columns: {', '.join(sorted(required - set(data.columns)))}"
            )
    except ImportError as exc:
        raise PredictionEstimateRepositoryError(
            "The spatial estimate requires pandas and NumPy to read cached model inputs."
        ) from exc
    except ValueError as exc:
        raise PredictionEstimateRepositoryError(
            f"Cached model-input grid for {region_id} is missing NDVI/NDBI: {exc}"
        ) from exc
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise PredictionEstimateRepositoryError(
            f"Could not read cached model-input grid for {region_id}: {exc}"
        ) from exc
    if "ndvi_valid" in data:
        data = data[data["ndvi_valid"].astype(str).str.casefold().eq("true")]
    if "ndbi_valid" in data:
        data = data[data["ndbi_valid"].astype(str).str.casefold().eq("true")]
    data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=["ndvi", "ndbi"])
    data = data[
        data["ndvi"].between(-1, 1) & data["ndbi"].between(-1, 1)
    ]
    if data.empty:
        return None, None, f"No valid paired NDVI and NDBI cells are cached for {region_id}."
    return float(data["ndvi"].mean()), float(data["ndbi"].mean()), None


def _unavailable_model(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason": reason,
        "training_districts": [],
        "test_districts": [],
        "training_cell_count": 0,
        "test_cell_count": 0,
    }


def _unavailable_estimate(
    region_id: str,
    season_year: int,
    reason: str,
    *,
    training_cell_count: int = 0,
    test_cell_count: int = 0,
    training_districts: list[str] | None = None,
    test_districts: list[str] | None = None,
) -> PredictionEstimate:
    return PredictionEstimate(
        region_id=region_id,
        season_year=season_year,
        model_status="unavailable",
        model_name=MODEL_NAME,
        target="Cached cell-level Landsat LST in °C; spatial estimation, not future heat",
        target_source=LST_SOURCE,
        validation_method=VALIDATION_METHOD,
        training_districts=training_districts or [],
        test_districts=test_districts or [],
        training_cell_count=training_cell_count,
        test_cell_count=test_cell_count,
        training_district_count=len(training_districts or []),
        test_district_count=len(test_districts or []),
        r_squared=None,
        mean_absolute_error_c=None,
        p90_absolute_error_c=None,
        evaluation_resolution_m=None,
        evaluation_start_date=None,
        evaluation_end_date=None,
        inputs=[],
        feature_importance=[],
        model_intercept_c=None,
        ndvi_coefficient_c_per_index=None,
        ndbi_coefficient_c_per_index=None,
        scenario_ndvi_mean=None,
        scenario_ndbi_mean=None,
        scenario_baseline_lst_c=None,
        scenario_error_bound_c=None,
        scenario_reason=reason,
        reason=reason,
    )
