from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_version: str = "0.1.0"
    database_url: str = "postgresql+psycopg://kizuna:kizuna@localhost:5432/kizuna"
    use_fixtures_only: bool = True
    youtube_api_key: str = ""


settings = Settings()
