from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import Artifact, Membership, Tenant, User


class IdentityRepository:
    """Every tenant-facing read requires tenant_id in the SQL predicate."""

    async def get_user_by_email(self, session: AsyncSession, *, email: str) -> User | None:
        result = await session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_user_for_tenant(
        self, session: AsyncSession, *, tenant_id: str, user_id: str
    ) -> tuple[User, Membership, Tenant] | None:
        result = await session.execute(
            select(User, Membership, Tenant)
            .join(Membership, Membership.user_id == User.id)
            .join(Tenant, Tenant.id == Membership.tenant_id)
            .where(
                Membership.tenant_id == tenant_id,
                Membership.user_id == user_id,
                Tenant.id == tenant_id,
            )
        )
        return result.one_or_none()

    async def list_memberships(
        self, session: AsyncSession, *, tenant_id: str, user_id: str
    ) -> list[Membership]:
        result = await session.execute(
            select(Membership).where(
                Membership.tenant_id == tenant_id, Membership.user_id == user_id
            )
        )
        return list(result.scalars())


class ArtifactRepository:
    """Artifact reads always carry the caller's tenant predicate."""

    async def get(
        self, session: AsyncSession, *, tenant_id: str, artifact_id: str
    ) -> Artifact | None:
        result = await session.execute(
            select(Artifact).where(Artifact.tenant_id == tenant_id, Artifact.id == artifact_id)
        )
        return result.scalar_one_or_none()

    async def find_by_hash(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        content_sha256: str,
        artifact_role: str,
    ) -> Artifact | None:
        result = await session.execute(
            select(Artifact).where(
                Artifact.tenant_id == tenant_id,
                Artifact.content_sha256 == content_sha256,
                Artifact.artifact_role == artifact_role,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_external_reference(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        external_request_reference: str,
    ) -> Artifact | None:
        result = await session.execute(
            select(Artifact)
            .where(
                Artifact.tenant_id == tenant_id,
                Artifact.external_request_reference == external_request_reference,
                Artifact.status == "accepted",
            )
            .order_by(Artifact.created_at.desc())
        )
        return result.scalars().first()

    async def count_for_intake(
        self, session: AsyncSession, *, tenant_id: str, intake_id: str
    ) -> int:
        result = await session.execute(
            select(func.count(Artifact.id)).where(
                Artifact.tenant_id == tenant_id,
                Artifact.intake_id == intake_id,
                Artifact.status != "rejected",
            )
        )
        return int(result.scalar_one())

    async def total_size_for_intake(
        self, session: AsyncSession, *, tenant_id: str, intake_id: str
    ) -> int:
        result = await session.execute(
            select(func.coalesce(func.sum(Artifact.size_bytes), 0)).where(
                Artifact.tenant_id == tenant_id,
                Artifact.intake_id == intake_id,
                Artifact.status != "rejected",
            )
        )
        return int(result.scalar_one())

    async def list_for_tenant(
        self, session: AsyncSession, *, tenant_id: str, limit: int = 100
    ) -> list[Artifact]:
        result = await session.execute(
            select(Artifact)
            .where(Artifact.tenant_id == tenant_id)
            .order_by(Artifact.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def list_expired_for_tenant(
        self, session: AsyncSession, *, tenant_id: str, now: datetime | None = None
    ) -> list[Artifact]:
        cutoff = now or datetime.now(UTC)
        result = await session.execute(
            select(Artifact).where(
                Artifact.tenant_id == tenant_id,
                Artifact.status == "accepted",
                Artifact.expires_at.is_not(None),
                Artifact.expires_at <= cutoff,
            )
        )
        return list(result.scalars())
