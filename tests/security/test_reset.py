import pytest

from scripts.reset_demo import validate_reset_target


def test_reset_requires_confirmation() -> None:
    with pytest.raises(ValueError, match="confirm-reset"):
        validate_reset_target(
            database_url="postgresql+asyncpg://app:app@localhost:5432/ops_intake",
            bucket="ops-intake-demo",
            app_env="development",
            confirmed=False,
        )


def test_reset_rejects_wrong_database() -> None:
    with pytest.raises(ValueError, match="unapproved database"):
        validate_reset_target(
            database_url="postgresql+asyncpg://app:app@localhost:5432/customer_production",
            bucket="ops-intake-demo",
            app_env="development",
            confirmed=True,
        )


def test_reset_rejects_non_development() -> None:
    with pytest.raises(ValueError, match="development"):
        validate_reset_target(
            database_url="postgresql+asyncpg://app:app@localhost:5432/ops_intake",
            bucket="ops-intake-demo",
            app_env="production",
            confirmed=True,
        )
