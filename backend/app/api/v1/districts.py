from fastapi import APIRouter, HTTPException

from app.core.settings import get_settings
from app.repositories.districts import DistrictBoundaryError, load_district_boundaries

router = APIRouter(prefix="/api/v1", tags=["districts"])


@router.get("/districts")
def get_district_boundaries() -> dict:
    try:
        return load_district_boundaries(get_settings().cache_dir)
    except DistrictBoundaryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
