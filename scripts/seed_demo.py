import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from apps.api.app.auth.service import hash_password
from apps.api.app.config.settings import get_settings
from apps.api.app.db.session import create_session_factory
from packages.db.models import Base, Membership, Tenant, User

DEMO_PASSWORD = "Demo-Only-Password-2026!"

TENANTS = (
    ("tenant-a", "Harborline Logistics Demo A"),
    ("tenant-b", "Harborline Logistics Demo B"),
)

USERS = (
    ("user-a-admin", "admin-a@harborline.example", "Tenant A Admin", "tenant-a", "admin"),
    (
        "user-a-reviewer",
        "reviewer-a@harborline.example",
        "Tenant A Reviewer",
        "tenant-a",
        "reviewer",
    ),
    ("user-a-viewer", "viewer-a@harborline.example", "Tenant A Viewer", "tenant-a", "viewer"),
    ("user-b-admin", "admin-b@harborline.example", "Tenant B Admin", "tenant-b", "admin"),
)


async def seed() -> None:
    settings = get_settings()
    factory, engine = create_session_factory(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        for tenant_id, name in TENANTS:
            tenant = await session.get(Tenant, tenant_id)
            if tenant is None:
                session.add(
                    Tenant(
                        id=tenant_id,
                        name=name,
                        status="active",
                        created_at=datetime.now(UTC),
                    )
                )
        await session.flush()
        for user_id, email, display_name, tenant_id, role in USERS:
            user = await session.get(User, user_id)
            if user is None:
                user = User(
                    id=user_id,
                    email=email,
                    display_name=display_name,
                    password_hash=hash_password(DEMO_PASSWORD),
                    status="active",
                    created_at=datetime.now(UTC),
                )
                session.add(user)
                await session.flush()
            membership = await session.scalar(
                select(Membership).where(
                    Membership.tenant_id == tenant_id, Membership.user_id == user_id
                )
            )
            if membership is None:
                session.add(
                    Membership(
                        id=f"membership-{tenant_id}-{user_id}",
                        tenant_id=tenant_id,
                        user_id=user_id,
                        role=role,
                        status="active",
                        created_at=datetime.now(UTC),
                    )
                )
        await session.commit()
    await engine.dispose()
    print("Seeded synthetic tenants/users. Demo password is documented only for local development.")


if __name__ == "__main__":
    asyncio.run(seed())
