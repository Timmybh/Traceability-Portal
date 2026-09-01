from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Web Truy suất"
    sqlserver_driver: str = "ODBC Driver 18 for SQL Server"
    sqlserver_host: str
    sqlserver_port: int = 1433
    sqlserver_database: str = "eGMF"
    sqlserver_user: str
    sqlserver_password: str
    sqlserver_encrypt: bool = True
    sqlserver_trust_server_certificate: bool = True
    sqlserver_connection_timeout: int = Field(default=5, ge=1, le=60)

    sqlquery: str
    sqlquery_image: str
    sqlquery_po: str
    sqlquery_lot: str
    sqlquery_new: str | None = None
    sqlquery_new_file: str | None = None
    image_allowed_host: str = "10.8.0.72:9231"
    image_timeout_seconds: int = Field(default=15, ge=1, le=120)
    image_cache_seconds: int = Field(default=3600, ge=0, le=86400)
    image_metadata_cache_seconds: int = Field(default=60, ge=1, le=3600)
    document_base_url: str = "http://10.8.0.72:9231/PhieuDieuTiet"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
