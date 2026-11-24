from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.core.settings import get_settings
from app.repositories.analytics import (
    AnalyticsRepositoryError,
    load_environmental_analytics,
)
from app.schemas.analytics import AnalyticsResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["environmental analytics"])


@router.get("/regions", response_model=AnalyticsResponse)
def get_environmental_analytics(
    season_year: Annotated[int, Query(ge=2013, le=9998)] = 2026,
) -> AnalyticsResponse:
    try:
        return load_environmental_analytics(
            get_settings().cache_dir,
            season_year=season_year,
        )
    except AnalyticsRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
