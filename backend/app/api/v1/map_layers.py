from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path as PathParameter
from fastapi.responses import Response

from app.core.settings import get_settings
from app.services.map_layers import (
    MapLayerError,
    render_lst_tile,
    render_satellite_tile,
)

router = APIRouter(prefix="/api/v1/map", tags=["map layers"])


@router.get("/lst/{zoom}/{x}/{y}.png", response_class=Response)
def get_lst_tile(
    zoom: Annotated[int, PathParameter(ge=0, le=13)],
    x: Annotated[int, PathParameter(ge=0)],
    y: Annotated[int, PathParameter(ge=0)],
) -> Response:
    try:
        tile = render_lst_tile(
            get_settings().cache_dir,
            zoom=zoom,
            x=x,
            y=y,
        )
    except MapLayerError as exc:
        status_code = 404 if "unavailable" in str(exc).lower() else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return Response(
        content=tile,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=900"},
    )


@router.get("/{layer}/{zoom}/{x}/{y}.png", response_class=Response)
def get_satellite_layer_tile(
    layer: Literal["ndvi", "ndbi", "ndwi"],
    zoom: Annotated[int, PathParameter(ge=0, le=13)],
    x: Annotated[int, PathParameter(ge=0)],
    y: Annotated[int, PathParameter(ge=0)],
) -> Response:
    try:
        tile = render_satellite_tile(
            get_settings().cache_dir,
            layer=layer,
            zoom=zoom,
            x=x,
            y=y,
        )
    except MapLayerError as exc:
        status_code = 404 if "unavailable" in str(exc).lower() else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return Response(
        content=tile,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=900"},
    )
