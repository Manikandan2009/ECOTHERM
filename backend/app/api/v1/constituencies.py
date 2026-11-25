from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from app.core.http_cache import etag_matches, file_version_etag
from app.core.settings import get_settings
from app.repositories.constituencies import (
    ConstituencyBoundaryError,
    load_constituencies,
)

router = APIRouter(prefix="/api/v1", tags=["constituencies"])


@router.get("/constituencies", response_model=dict)
def get_constituencies(
    request: Request,
    district_id: str | None = Query(default=None, pattern=r"^[a-z0-9_]+$"),
) -> dict[str, Any] | Response:
    cache_dir = get_settings().cache_dir
    try:
        data = load_constituencies(
            cache_dir,
            district_id=district_id,
        )
    except ConstituencyBoundaryError as exc:
        status_code = 404 if district_id and str(exc).startswith("No Tamil Nadu") else 503
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    paths = (
        cache_dir / "processed" / "boundaries" / "constituencies.geojson",
        cache_dir / "processed" / "boundaries" / "constituencies_manifest.json",
    )
    try:
        etag = file_version_etag(
            paths,
            vary_by=f"district_id={district_id or ''}",
        )
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not inspect cached constituency boundary versions: {exc}",
        ) from exc
    headers = {
        "Cache-Control": "public, max-age=300",
        "ETag": etag,
        "Vary": "Accept-Encoding",
    }
    if etag_matches(request, etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(content=data, headers=headers)
