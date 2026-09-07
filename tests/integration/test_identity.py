from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from apps.api.app.auth.service import hash_password
from apps.api.app.main import create_app
from packages.db.models import Membership, Tenant, User


async def seed_identity(factory) -> None:
    async with factory() as session:
        session.add_all(
            [
                Tenant(
                    id="tenant-a",
                    name="Tenant A",
                    status="active",
                    created_at=datetime.now(UTC),
                ),
                Tenant(
                    id="tenant-b",
                    name="Tenant B",
                    status="active",
                    created_at=datetime.now(UTC),
                ),
                User(
                    id="user-a",
                    email="a@example.test",
                    display_name="A",
                    password_hash=hash_password("pw"),
                    status="active",
                    created_at=datetime.now(UTC),
                ),
                User(
                    id="user-b",
                    email="b@example.test",
                    display_name="B",
                    password_hash=hash_password("pw"),
                    status="active",
                    created_at=datetime.now(UTC),
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
                    created_at=datetime.now(UTC),
                ),
                Membership(
                    id="membership-a-viewer",
                    tenant_id="tenant-a",
                    user_id="user-b",
                    role="viewer",
                    status="active",
                    created_at=datetime.now(UTC),
                ),
                Membership(
                    id="membership-b",
                    tenant_id="tenant-b",
                    user_id="user-b",
                    role="reviewer",
                    status="active",
                    created_at=datetime.now(UTC),
                ),
            ]
        )
        await session.commit()


@pytest.mark.asyncio
async def test_login_and_tenant_role_isolation(db_session_factory, test_settings) -> None:
    await seed_identity(db_session_factory)
    app = create_app(test_settings, session_factory=db_session_factory)
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login", json={"email": "a@example.test", "password": "pw"}
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-a"}

        assert client.get("/api/viewer/ping", headers=headers).status_code == 200
        assert client.get("/api/reviewer/ping", headers=headers).status_code == 200
        assert client.get("/api/admin/ping", headers=headers).status_code == 200

        cross_tenant = {**headers, "X-Tenant-ID": "tenant-b"}
        assert client.get("/api/viewer/ping", headers=cross_tenant).status_code == 404


@pytest.mark.asyncio
async def test_membership_status_is_rechecked(db_session_factory, test_settings) -> None:
    await seed_identity(db_session_factory)
    app = create_app(test_settings, session_factory=db_session_factory)
    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login", json={"email": "b@example.test", "password": "pw"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-a"}
        assert client.get("/api/viewer/ping", headers=headers).status_code == 200

        async with db_session_factory() as session:
            membership = await session.scalar(
                select(Membership).where(
                    Membership.tenant_id == "tenant-a", Membership.user_id == "user-b"
                )
            )
            membership.status = "suspended"
            await session.commit()

        assert client.get("/api/viewer/ping", headers=headers).status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit_fails_closed_without_revealing_auth_state(
    db_session_factory, test_settings
) -> None:
    await seed_identity(db_session_factory)
    limited_settings = test_settings.model_copy(update={"auth_rate_limit_per_window": 1})
    app = create_app(limited_settings, session_factory=db_session_factory)
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/auth/login", json={"email": "a@example.test", "password": "pw"}
            ).status_code
            == 200
        )
        limited = client.post("/api/auth/login", json={"email": "a@example.test", "password": "pw"})
        assert limited.status_code == 429
        assert limited.json()["detail"] == "too many requests"
