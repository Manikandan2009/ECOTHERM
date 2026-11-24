from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.core.settings import get_settings
from app.repositories.predictions import (
    PredictionRepositoryError,
    load_prediction_status,
)
from app.repositories.prediction_estimates import (
    PredictionEstimateRepositoryError,
    load_prediction_estimate,
)
from app.schemas.prediction_estimate import PredictionEstimate
from app.schemas.predictions import PredictionStatus

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])


@router.get("/status", response_model=PredictionStatus)
def get_prediction_status(
    region_id: Annotated[
        str,
        Query(
            pattern=(
                r"^(tamil_nadu|chennai|coimbatore|madurai|"
                r"district_[a-z0-9_]+|constituency_[a-z0-9_]+)$"
            )
        ),
    ] = "tamil_nadu",
) -> PredictionStatus:
    settings = get_settings()
    try:
        return load_prediction_status(
            settings.cache_dir / "processed" / "ecotherm.sqlite",
            region_id=region_id,
        )
    except PredictionRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/estimate", response_model=PredictionEstimate)
def get_spatial_prediction_estimate(
    region_id: Annotated[
        str,
        Query(
            pattern=r"^(tamil_nadu|district_[a-z0-9_]+|constituency_[a-z0-9_]+)$"
        ),
    ] = "tamil_nadu",
    season_year: Annotated[int, Query(ge=2013, le=9998)] = 2026,
) -> PredictionEstimate:
    try:
        return load_prediction_estimate(
            get_settings().cache_dir,
            region_id=region_id,
            season_year=season_year,
        )
    except PredictionEstimateRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
