import argparse
import asyncio
from urllib.parse import urlparse

from sqlalchemy import delete

from apps.api.app.config.settings import get_settings
from apps.api.app.db.session import create_session_factory
from packages.db.models import Membership, Tenant, User


def validate_reset_target(*, database_url: str, bucket: str, app_env: str, confirmed: bool) -> None:
    parsed = urlparse(database_url)
    if not confirmed:
        raise ValueError("reset requires --confirm-reset")
    if app_env != "development":
        raise ValueError("reset is allowed only in development")
    if parsed.path.rstrip("/") not in {"/ops_intake", "/ops_intake_test"}:
        raise ValueError("refusing to reset an unapproved database name")
    if bucket != "ops-intake-demo":
        raise ValueError("refusing to reset an unapproved storage bucket")


async def reset() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-reset", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    validate_reset_target(
        database_url=settings.database_url,
        bucket=settings.object_storage_bucket,
        app_env=settings.app_env,
        confirmed=args.confirm_reset,
    )
    factory, engine = create_session_factory(settings)
    async with factory() as session:
        await session.execute(delete(Membership))
        await session.execute(delete(User))
        await session.execute(delete(Tenant))
        await session.commit()
    await engine.dispose()
    print("Reset synthetic identity data only; storage object deletion is deferred")
    print("until artifact ingestion exists.")


if __name__ == "__main__":
    asyncio.run(reset())
