"""Application configuration."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DB = f"sqlite:///{_BACKEND_DIR / 'energyhub.db'}"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "EnergyHub"
    debug: bool = False

    # Database
    database_url: str = _DEFAULT_DB

    # File upload settings
    upload_dir: str = "./uploads"
    max_upload_size: int = 50 * 1024 * 1024  # 50MB

    # Network provider tariff sources
    tariff_cache_ttl: int = 86400  # 24 hours
    auth_session_ttl_hours: int = 24 * 7

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
