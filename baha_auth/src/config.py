"""Cấu hình chuẩn cho dịch vụ phân quyền BAHA Auth."""

from typing import Optional
from pathlib import Path

AUTH_DB_PATH = (Path(__file__).resolve().parents[2] / "sin_content_api" / "baha_auth_live.db").resolve().as_posix()

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.auth",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Dịch vụ phân quyền BAHA GROUP"
    app_version: str = "1.0.0"
    app_env: str = "offline"
    debug: bool = False

    # Cơ sở dữ liệu phân quyền tách biệt với DATABASE_URL của API nghiệp vụ.
    database_url: Optional[str] = Field(default=f"sqlite:///{AUTH_DB_PATH}", validation_alias="BAHA_AUTH_DATABASE_URL")

    jwt_secret_key: Optional[str] = Field(default="sin-dev-secret-do-not-use-in-production", validation_alias="BAHA_AUTH_JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_issuer: Optional[str] = Field(default="baha-auth-issuer", validation_alias="BAHA_AUTH_JWT_ISSUER")
    jwt_audience: Optional[str] = Field(default="sin-content-test", validation_alias="BAHA_AUTH_JWT_AUDIENCE")
    worker_jwt_audience: Optional[str] = Field(default=None, validation_alias="BAHA_AUTH_WORKER_AUDIENCE")
    worker_jwt_subject: Optional[str] = Field(default=None, validation_alias="BAHA_AUTH_WORKER_SUBJECT")
    authz_base_url: Optional[str] = Field(default=None, validation_alias="BAHA_AUTHZ_BASE_URL")
    policy_version: str = "1.0.0"

    force_rls: bool = True
    enforce_strict_tenant_isolation: bool = True


settings = Settings()
