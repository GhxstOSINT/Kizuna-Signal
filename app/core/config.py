from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="KIZUNA_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Kizuna Signal API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./kizuna.db"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    demo_mode: bool = False
    live_sources: bool = True  # KIZUNA_LIVE_SOURCES=false falls back to offline test signals
    youtube_api_key: str | None = None
    source_cache_dir: str | None = ".cache/sources"  # 24h evidence cache; empty disables
    source_contact_url: str = "https://github.com/GhxstOSINT/TSLAS-Japan-Day-Hackathon"
    log_level: str = "INFO"
    model_version: str = "kizuna-census-ridge-1.0.0"
    feature_version: str = "public-signals-0.1.0"
    scoring_version: str = "market-potential-0.2.0"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
