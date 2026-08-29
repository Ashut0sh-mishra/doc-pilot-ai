from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DocPilot API"
    app_env: str = "development"
    database_url: str = "sqlite:///./docpilot.db"
    storage_bucket: str = "docpilot-records"
    storage_region: str = "ap-south-1"
    max_upload_mb: int = 20
    upload_dir: str = "./uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
