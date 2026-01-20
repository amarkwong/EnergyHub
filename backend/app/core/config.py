"""Application configuration."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "EnergyHub"
    debug: bool = False

    # Database
    database_url: str = "postgresql://localhost:5432/energyhub"

    # File upload settings
    upload_dir: str = "./uploads"
    max_upload_size: int = 50 * 1024 * 1024  # 50MB

    # Network provider tariff sources
    tariff_cache_ttl: int = 86400  # 24 hours

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
