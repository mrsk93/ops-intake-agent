from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import Membership, Tenant, User


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
