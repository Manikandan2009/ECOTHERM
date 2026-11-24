from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.core.settings import get_settings
from app.schemas.inspection import MapInspectionResponse
from app.services.map_inspection import MapInspectionError, inspect_map_point

router = APIRouter(tags=["map inspection"])


@router.get(
    "/api/inspect",
    response_model=MapInspectionResponse,
    operation_id="inspect_map_point",
)
@router.get(
    "/api/v1/inspect",
    response_model=MapInspectionResponse,
    operation_id="inspect_map_point_v1",
)
async def get_map_inspection(
    latitude: Annotated[float, Query(alias="lat", ge=-90, le=90)],
    longitude: Annotated[float, Query(alias="lon", ge=-180, le=180)],
) -> MapInspectionResponse:
    settings = get_settings()
    try:
        return await inspect_map_point(
            cache_dir=settings.cache_dir,
            latitude=latitude,
            longitude=longitude,
            timeout_seconds=settings.open_meteo_timeout_seconds,
        )
    except MapInspectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
