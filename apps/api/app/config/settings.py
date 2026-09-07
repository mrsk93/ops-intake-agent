from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/ops_intake"
    redis_url: str = "redis://localhost:6379/0"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_access_key: str = "minioadmin"
    object_storage_secret_key: str = "minioadmin"
    object_storage_bucket: str = "ops-intake-demo"
    artifact_storage_provider: Literal["local", "s3", "fake"] = "local"
    artifact_storage_root: str = ".data/objects"
    max_artifacts_per_intake: int = Field(default=10, ge=1, le=100)
    max_artifact_bytes: int = Field(default=15 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    max_total_intake_bytes: int = Field(default=40 * 1024 * 1024, ge=1, le=200 * 1024 * 1024)
    max_pdf_pages: int = Field(default=100, ge=1, le=1000)
    max_workbook_sheets: int = Field(default=10, ge=1, le=100)
    max_table_rows: int = Field(default=10_000, ge=1, le=1_000_000)
    max_extracted_text_chars: int = Field(default=1_000_000, ge=1_000, le=10_000_000)
    artifact_retention_days: int = Field(default=30, ge=1, le=3650)
    derived_text_retention_days: int = Field(default=30, ge=1, le=3650)
    raw_provider_output_retention_days: int = Field(default=7, ge=1, le=3650)
    canonical_metadata_retention_days: int = Field(default=90, ge=1, le=3650)
    auth_jwt_secret: str = "local-only-demo-secret-change-me"
    auth_token_ttl_minutes: int = Field(default=30, ge=5, le=1440)
    enable_demo_controls: bool = True
    model_provider: Literal["fake", "openai"] = "fake"
    ocr_provider: Literal["fake", "local"] = "fake"
    ops_provider: Literal["mock", "external"] = "mock"
    rate_limit_provider: Literal["memory", "redis"] = "memory"
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    auth_rate_limit_per_window: int = Field(default=20, ge=1, le=1000)
    approval_rate_limit_per_window: int = Field(default=20, ge=1, le=1000)
    credential_encryption_provider: Literal["unconfigured", "fake", "external"] = "unconfigured"
    openai_api_key: str | None = None
    openai_model: str | None = None
    model_timeout_seconds: float = Field(default=45.0, ge=1, le=300)
    max_model_output_tokens: int = Field(default=1200, ge=100, le=10_000)
    extraction_prompt_version: str = "prompt-1.0"
    extraction_schema_version: str = "1.0"

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.app_env == "production":
            if self.enable_demo_controls:
                raise ValueError("ENABLE_DEMO_CONTROLS must be false in production")
            if (
                self.model_provider == "fake"
                or self.ocr_provider == "fake"
                or self.ops_provider == "mock"
            ):
                raise ValueError("fake/demo providers are forbidden in production")
            if self.auth_jwt_secret == "local-only-demo-secret-change-me":
                raise ValueError("AUTH_JWT_SECRET must be explicitly configured in production")
            if self.artifact_storage_provider in {"local", "fake"}:
                raise ValueError("ARTIFACT_STORAGE_PROVIDER must be s3 in production")
            if self.rate_limit_provider != "redis":
                raise ValueError("production requires a Redis rate limit provider")
            if self.credential_encryption_provider != "external":
                raise ValueError("production requires an external credential encryption provider")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
