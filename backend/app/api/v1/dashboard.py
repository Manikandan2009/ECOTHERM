from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.core.settings import get_settings
from app.repositories.dashboard import (
    DashboardRepositoryError,
    load_dashboard_summary,
)
from app.schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/api/v1", tags=["dashboard"])

REGION_RESOLUTIONS = {
    "tamil_nadu": 1000,
    "chennai": 100,
    "coimbatore": 100,
    "madurai": 100,
}


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    region_id: Annotated[
        str,
        Query(
            pattern=(
                r"^(tamil_nadu|chennai|coimbatore|madurai|"
                r"district_[a-z0-9_]+|constituency_[a-z0-9_]+)$"
            )
        ),
    ] = "tamil_nadu",
    season_year: Annotated[int, Query(ge=2013, le=9998)] = 2026,
) -> DashboardSummary:
    settings = get_settings()
    try:
        return load_dashboard_summary(
            settings.cache_dir / "processed" / "ecotherm.sqlite",
            region_id=region_id,
            season_year=season_year,
            grid_resolution_m=REGION_RESOLUTIONS.get(region_id, 1000),
        )
    except DashboardRepositoryError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
