from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.weather import router as weather_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.districts import router as districts_router
from app.api.v1.constituencies import router as constituencies_router
from app.api.v1.inspect import router as inspect_router
from app.api.v1.map_layers import router as map_layers_router
from app.api.v1.satellite import router as satellite_router
from app.api.v1.predictions import router as predictions_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.priorities import router as priorities_router
from app.core.settings import get_settings

app = FastAPI(
    title="ECOTHERM API",
    description="File-backed urban heat data services for Tamil Nadu.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(weather_router)
app.include_router(dashboard_router)
app.include_router(districts_router)
app.include_router(constituencies_router)
app.include_router(inspect_router)
app.include_router(map_layers_router)
app.include_router(satellite_router)
app.include_router(predictions_router)
app.include_router(analytics_router)
app.include_router(priorities_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "data_mode": "cached-files",
        "earth_engine_project_configured": bool(settings.earth_engine_project_id),
        "cache_directory_exists": settings.cache_dir.is_dir(),
    }
