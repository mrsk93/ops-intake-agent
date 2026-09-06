import asyncio

import dramatiq

from apps.api.app.config.settings import get_settings
from apps.api.app.db.session import create_session_factory
from packages.artifacts.service import ArtifactIngestionService
from packages.providers.storage import LocalFileStorage, S3Storage


@dramatiq.actor
def health_task() -> str:
    """M1 no-op task proving the worker boundary is wired without side effects."""
    return "ok"


@dramatiq.actor
def expire_artifacts_for_tenant(tenant_id: str) -> int:
    """Run retention for one tenant; the caller must provide tenant scope explicitly."""
    return asyncio.run(_expire_artifacts_for_tenant(tenant_id))


async def _expire_artifacts_for_tenant(tenant_id: str) -> int:
    settings = get_settings()
    if settings.artifact_storage_provider == "s3":
        storage = S3Storage(
            endpoint=settings.object_storage_endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            bucket=settings.object_storage_bucket,
        )
    else:
        storage = LocalFileStorage(settings.artifact_storage_root)
    factory, engine = create_session_factory(settings)
    try:
        async with factory() as session:
            service = ArtifactIngestionService(
                storage, retention_days=settings.artifact_retention_days
            )
            return await service.expire_for_tenant(session, tenant_id=tenant_id)
    finally:
        await engine.dispose()
