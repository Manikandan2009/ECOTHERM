from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.core.settings import get_settings
from app.repositories.satellite import (
    SatelliteRepositoryError,
    load_constituency_scatter,
    load_satellite_summary,
)
from app.schemas.satellite import SatelliteAnalysisSummary, SatelliteScatterSummary

router = APIRouter(prefix="/api/v1/satellite", tags=["satellite analysis"])


@router.get("/scatter", response_model=SatelliteScatterSummary)
def get_constituency_scatter(
    constituency_id: Annotated[
        str,
        Query(pattern=r"^ac_[0-9]{3}_[a-z0-9_]+$"),
    ],
    season_year: Annotated[int, Query(ge=2013, le=9998)] = 2026,
) -> SatelliteScatterSummary:
    try:
        return load_constituency_scatter(
            get_settings().cache_dir,
            constituency_id=constituency_id,
            season_year=season_year,
        )
    except SatelliteRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/summary", response_model=SatelliteAnalysisSummary)
def get_satellite_summary(
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
) -> SatelliteAnalysisSummary:
    settings = get_settings()
    try:
        return load_satellite_summary(
            settings.cache_dir / "processed" / "ecotherm.sqlite",
            region_id=region_id,
            season_year=season_year,
            cache_dir=settings.cache_dir,
        )
    except SatelliteRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
