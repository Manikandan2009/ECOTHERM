from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.core.settings import get_settings
from app.repositories.priorities import (
    PrioritiesRepositoryError,
    load_constituency_priorities,
)
from app.schemas.priorities import PrioritiesResponse

router = APIRouter(prefix="/api/v1/priorities", tags=["priorities and budget"])


@router.get("/constituencies", response_model=PrioritiesResponse)
def get_constituency_priorities(
    season_year: Annotated[int, Query(ge=2013, le=9998)] = 2026,
) -> PrioritiesResponse:
    try:
        return load_constituency_priorities(
            get_settings().cache_dir,
            season_year=season_year,
        )
    except PrioritiesRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
