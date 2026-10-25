from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import REPO_ROOT, resolve

# Settings holding a folder; relative values are anchored to the repo root (see app.core.paths).
PATH_FIELDS = (
    "survey_dir",
    "anilist_raw_dir",
    "models_dir",
    "csv_dir",
    "reports_dir",
    "trends_raw_dir",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
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
    demo_mode: bool = True
    # Sign-in. public_url is the address the browser uses (the dashboard, which proxies /api), so
    # OAuth callbacks are `<public_url>/api/v1/auth/<provider>/callback`. A provider with no
    # client id/secret is reported as not configured.
    public_url: str = "http://localhost:4173"
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    session_ttl_days: int = 30
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

    @model_validator(mode="after")
    def anchor_paths(self):
        for name in PATH_FIELDS:
            setattr(self, name, str(resolve(getattr(self, name))))
        return self

    # ML layer: state model, one-shot prediction, reports, collectors (KIZUNA_ prefix like the rest)
    use_fixtures_only: bool = True
    youtube_api_key: str = ""
    anilist_url: str = "https://graphql.anilist.co"
    anilist_timeout_s: float = 15.0
    anilist_max_retries: int = 3
    anilist_cache_ttl_s: int = 7 * 24 * 3600
    anilist_page_delay_s: float = 0.8  # AniList allows ~90 requests/minute
    anilist_raw_dir: str = "data/raw/anilist"
    models_dir: str = "models"
    csv_dir: str = "data/tables"
    reports_dir: str = "data/reports"
    trends_raw_dir: str = "data/raw/google_trends"
    trends_anchor: str = "Death Note"  # mid-scale: "anime" is too large, titles round to 0
    trends_delay_s: float = 6.0
    trends_backoff_s: float = 30.0
    trends_max_retries: int = 3
    trends_circuit_breaker: int = 4  # consecutive 429s before the run stops
    trends_max_requests: int = 1000  # per run; Google blocks heavy callers


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()  # module-level alias used by the ML layer
