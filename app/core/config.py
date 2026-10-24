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
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:3000"]
    demo_mode: bool = True
    source_timeout_seconds: float = 10.0
    source_user_agent: str = (
        "KizunaSignal/0.1 (https://github.com/hexbyte-work; hackathon prototype)"
    )
    wikimedia_lookback_days: int = 90
    trends_geo: str = "IN"
    trends_benchmark: str = "One Piece"
    trends_cache_ttl_seconds: int = 6 * 3600
    trends_cooldown_seconds: int = 15 * 60
    anilist_cache_ttl_seconds: int = 24 * 3600
    anilist_cooldown_seconds: int = 60
    # Simulated rows, flagged PROXY. Set to data/survey to use only real survey rows.
    survey_dir: str = "data/synthetic"
    youtube_api_key: str = ""
    youtube_cache_ttl_seconds: int = 6 * 3600
    log_level: str = "INFO"
    model_version: str = "kizuna-baseline-0.1.0"
    feature_version: str = "public-signals-0.1.0"
    scoring_version: str = "market-potential-0.1.0"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
