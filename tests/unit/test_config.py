import pytest
from pydantic import ValidationError

from apps.api.app.config.settings import Settings


def test_production_rejects_demo_controls() -> None:
    with pytest.raises(ValidationError, match="ENABLE_DEMO_CONTROLS"):
        Settings(
            app_env="production",
            enable_demo_controls=True,
            model_provider="openai",
            ocr_provider="local",
            ops_provider="external",
            auth_jwt_secret="real-secret",
        )


def test_production_rejects_fake_providers() -> None:
    with pytest.raises(ValidationError, match="fake/demo providers"):
        Settings(app_env="production", enable_demo_controls=False, auth_jwt_secret="real-secret")


def test_production_requires_non_default_secret() -> None:
    with pytest.raises(ValidationError, match="AUTH_JWT_SECRET"):
        Settings(
            app_env="production",
            enable_demo_controls=False,
            model_provider="openai",
            ocr_provider="local",
            ops_provider="external",
        )


def test_development_allows_demo_defaults() -> None:
    settings = Settings(app_env="development")
    assert settings.model_provider == "fake"
