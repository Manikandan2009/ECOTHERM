from fastapi import APIRouter, HTTPException, Query

from app.core.settings import get_settings
from app.repositories.constituencies import (
    ConstituencyBoundaryError,
    load_constituencies,
)

router = APIRouter(prefix="/api/v1", tags=["constituencies"])


@router.get("/constituencies")
def get_constituencies(
    district_id: str | None = Query(default=None, pattern=r"^[a-z0-9_]+$"),
) -> dict:
    try:
        return load_constituencies(
            get_settings().cache_dir,
            district_id=district_id,
        )
    except ConstituencyBoundaryError as exc:
        status_code = 404 if district_id and str(exc).startswith("No Tamil Nadu") else 503
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
