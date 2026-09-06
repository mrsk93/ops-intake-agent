import argparse
import asyncio
from urllib.parse import urlparse

from sqlalchemy import delete, select

from apps.api.app.config.settings import get_settings
from apps.api.app.db.session import create_session_factory
from packages.db.models import Artifact, Membership, Tenant, User
from packages.db.repositories import ArtifactRepository
from packages.providers.storage import LocalFileStorage, S3Storage


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
    storage = _storage_for_settings(settings)
    async with factory() as session:
        tenants = list((await session.scalars(select(Tenant))).all())
        artifact_repository = ArtifactRepository()
        for tenant in tenants:
            for artifact in await artifact_repository.list_for_tenant(session, tenant_id=tenant.id):
                if artifact.storage_key:
                    await storage.delete(tenant_id=tenant.id, key=artifact.storage_key)
        await session.execute(delete(Artifact))
        await session.execute(delete(Membership))
        await session.execute(delete(User))
        await session.execute(delete(Tenant))
        await session.commit()
    await engine.dispose()
    print("Reset synthetic identity data and tenant-scoped demo artifacts.")


def _storage_for_settings(settings):
    if settings.artifact_storage_provider == "s3":
        return S3Storage(
            endpoint=settings.object_storage_endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            bucket=settings.object_storage_bucket,
        )
    return LocalFileStorage(settings.artifact_storage_root)


if __name__ == "__main__":
    asyncio.run(reset())
