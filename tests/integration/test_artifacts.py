from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import hash_password
from apps.api.app.main import create_app
from packages.artifacts.service import ArtifactIngestionService
from packages.db.models import Membership, Tenant, User
from packages.db.repositories import ArtifactRepository
from packages.providers.storage import LocalFileStorage
from packages.testkit.fakes import FakeStorage


async def seed_identity(factory) -> None:
    async with factory() as session:
        session.add_all(
            [
                Tenant(id="tenant-a", name="Tenant A", status="active"),
                Tenant(id="tenant-b", name="Tenant B", status="active"),
                User(
                    id="user-a",
                    email="a@example.test",
                    display_name="A",
                    password_hash=hash_password("pw"),
                    status="active",
                ),
                User(
                    id="user-b",
                    email="b@example.test",
                    display_name="B",
                    password_hash=hash_password("pw"),
                    status="active",
                ),
            ]
        )
        session.add_all(
            [
                Membership(
                    id="membership-a",
                    tenant_id="tenant-a",
                    user_id="user-a",
                    role="admin",
                    status="active",
                ),
                Membership(
                    id="membership-b",
                    tenant_id="tenant-b",
                    user_id="user-b",
                    role="admin",
                    status="active",
                ),
            ]
        )
        await session.commit()


@pytest.mark.asyncio
async def test_dedup_is_tenant_local_and_external_reference_flags_amendment(
    db_session_factory,
) -> None:
    await seed_identity(db_session_factory)
    storage = FakeStorage()
    service = ArtifactIngestionService(storage)
    async with db_session_factory() as session:
        first = await service.ingest_bytes(
            session,
            tenant_id="tenant-a",
            filename="request.csv",
            content=b"SKU,Quantity\nABC,1\n",
            declared_media_type="text/csv",
            external_request_reference="REQ-1",
        )
        duplicate = await service.ingest_bytes(
            session,
            tenant_id="tenant-a",
            filename="same.csv",
            content=b"SKU,Quantity\nABC,1\n",
            declared_media_type="text/csv",
            external_request_reference="REQ-1",
        )
        other_tenant = await service.ingest_bytes(
            session,
            tenant_id="tenant-b",
            filename="request.csv",
            content=b"SKU,Quantity\nABC,1\n",
            declared_media_type="text/csv",
            external_request_reference="REQ-1",
        )
        amendment = await service.ingest_bytes(
            session,
            tenant_id="tenant-a",
            filename="amendment.csv",
            content=b"SKU,Quantity\nABC,2\n",
            declared_media_type="text/csv",
            external_request_reference="REQ-1",
        )
        assert first.artifact.status == "accepted"
        assert duplicate.duplicate is True
        assert other_tenant.duplicate is False
        assert amendment.artifact.review_required is True
        assert amendment.artifact.amendment_of_artifact_id == first.artifact.id
        assert await storage.get(tenant_id="tenant-a", key=first.artifact.storage_key) == (
            b"SKU,Quantity\nABC,1\n"
        )
        with pytest.raises(KeyError):
            await storage.get(tenant_id="tenant-b", key=first.artifact.storage_key)

        repository = ArtifactRepository()
        tenant_a = await repository.list_for_tenant(session, tenant_id="tenant-a")
        tenant_b = await repository.list_for_tenant(session, tenant_id="tenant-b")
        assert {artifact.tenant_id for artifact in tenant_a} == {"tenant-a"}
        assert {artifact.tenant_id for artifact in tenant_b} == {"tenant-b"}


@pytest.mark.asyncio
async def test_retention_removes_content_but_preserves_expired_record(db_session_factory) -> None:
    await seed_identity(db_session_factory)
    storage = FakeStorage()
    service = ArtifactIngestionService(storage)
    async with db_session_factory() as session:
        result = await service.ingest_bytes(
            session,
            tenant_id="tenant-a",
            filename="request.csv",
            content=b"sku,quantity\nABC,1\n",
            declared_media_type="text/csv",
        )
        result.artifact.expires_at = datetime.now(UTC) - timedelta(days=1)
        await session.commit()
        expired = await service.expire_for_tenant(session, tenant_id="tenant-a")
        assert expired == 1
        assert result.artifact.status == "expired"
        assert result.artifact.storage_key is None
        with pytest.raises(KeyError):
            await storage.get(tenant_id="tenant-a", key="accepted/missing")


@pytest.mark.asyncio
async def test_api_upload_view_and_cross_tenant_read_are_scoped(
    db_session_factory, test_settings
) -> None:
    await seed_identity(db_session_factory)
    storage = FakeStorage()
    app = create_app(test_settings, session_factory=db_session_factory, storage_provider=storage)
    with TestClient(app) as client:
        token_a = client.post(
            "/api/auth/login", json={"email": "a@example.test", "password": "pw"}
        ).json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": "tenant-a"}
        response = client.post(
            "/api/artifacts",
            headers=headers_a,
            files={"file": ("request.csv", b"sku,quantity\nABC,1\n", "text/csv")},
        )
        assert response.status_code == 201
        artifact_id = response.json()["artifact"]["id"]
        assert (
            client.get(f"/api/artifacts/{artifact_id}/view", headers=headers_a).status_code == 200
        )

        token_b = client.post(
            "/api/auth/login", json={"email": "b@example.test", "password": "pw"}
        ).json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}", "X-Tenant-ID": "tenant-b"}
        assert client.get(f"/api/artifacts/{artifact_id}", headers=headers_b).status_code == 404
        assert (
            client.get(f"/api/artifacts/{artifact_id}/download", headers=headers_b).status_code
            == 404
        )


def test_local_storage_rejects_key_escape(tmp_path) -> None:
    storage = LocalFileStorage(tmp_path)
    with pytest.raises(ValueError, match="storage key"):
        storage._path("tenant-a", "../outside")
