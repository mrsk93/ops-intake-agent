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
    auth_jwt_secret: str = "local-only-demo-secret-change-me"
    auth_token_ttl_minutes: int = Field(default=30, ge=5, le=1440)
    enable_demo_controls: bool = True
    model_provider: Literal["fake", "openai"] = "fake"
    ocr_provider: Literal["fake", "local"] = "fake"
    ops_provider: Literal["mock", "external"] = "mock"
    openai_api_key: str | None = None
    openai_model: str | None = None

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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
