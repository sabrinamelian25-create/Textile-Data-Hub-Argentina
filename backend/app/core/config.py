from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Textile Data Hub Argentina API"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres@localhost:5432/textile_data_hub"
    test_database_url: str = "postgresql+psycopg://postgres@localhost:5432/textile_data_hub_test"
    raw_data_dir: str = str(Path(__file__).resolve().parents[2] / "data" / "raw")
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,*"
    enable_scheduler: bool = False
    auto_ingest_if_empty: bool = False
    http_timeout_seconds: float = 45.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
