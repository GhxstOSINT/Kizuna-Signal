from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_version: str = "0.1.0"
    database_url: str = "postgresql+psycopg://kizuna:kizuna@localhost:5432/kizuna"
    use_fixtures_only: bool = True
    youtube_api_key: str = ""
    anilist_url: str = "https://graphql.anilist.co"
    anilist_timeout_s: float = 15.0
    anilist_max_retries: int = 3
    anilist_cache_ttl_s: int = 7 * 24 * 3600
    anilist_page_delay_s: float = 0.8  # AniList allows ~90 requests/minute
    anilist_raw_dir: str = "data/raw/anilist"
    trends_raw_dir: str = "data/raw/google_trends"
    trends_anchor: str = "anime"
    trends_delay_s: float = 6.0
    trends_backoff_s: float = 30.0
    trends_max_retries: int = 3
    trends_max_requests: int = 1000  # per run; Google blocks heavy callers


settings = Settings()
