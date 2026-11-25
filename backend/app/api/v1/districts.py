from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.core.settings import get_settings
from app.core.http_cache import etag_matches, file_version_etag
from app.repositories.districts import DistrictBoundaryError, load_district_boundaries

router = APIRouter(prefix="/api/v1", tags=["districts"])


@router.get("/districts", response_model=dict)
def get_district_boundaries(
    request: Request,
) -> dict[str, Any] | Response:
    cache_dir = get_settings().cache_dir
    try:
        data = load_district_boundaries(cache_dir)
    except DistrictBoundaryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    paths = (
        cache_dir / "processed" / "boundaries" / "districts.geojson",
        cache_dir / "processed" / "boundaries" / "districts_manifest.json",
    )
    try:
        etag = file_version_etag(paths)
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not inspect cached district boundary versions: {exc}",
        ) from exc
    headers = {
        "Cache-Control": "public, max-age=300",
        "ETag": etag,
        "Vary": "Accept-Encoding",
    }
    if etag_matches(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=data, headers=headers)
