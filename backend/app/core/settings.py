from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ECOTHERM_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    earth_engine_project_id: str = "ecotherm-515613"
    cache_dir: Path = PROJECT_ROOT / "data" / "cache"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    open_meteo_timeout_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
