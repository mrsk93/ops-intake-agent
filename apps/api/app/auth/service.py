from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.config.settings import Settings
from packages.db.models import Membership, User
from packages.db.repositories import IdentityRepository
from packages.domain.identity import Role, TenantContext

PASSWORD_HASH = PasswordHash.recommended()


class AuthenticationError(ValueError):
    pass


def hash_password(password: str) -> str:
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_HASH.verify(password, password_hash)


def issue_token(*, user_id: str, settings: Settings) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.auth_token_ttl_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expires_at}, settings.auth_jwt_secret, algorithm="HS256"
    )


def decode_token(token: str, settings: Settings) -> str:
    try:
        payload = jwt.decode(token, settings.auth_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise AuthenticationError("invalid access token") from exc
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise AuthenticationError("invalid access token subject")
    return user_id


class AuthService:
    def __init__(self, repository: IdentityRepository | None = None) -> None:
        self.repository = repository or IdentityRepository()

    async def login(
        self, session: AsyncSession, *, email: str, password: str, settings: Settings
    ) -> tuple[User, list[Membership]]:
        user = await self.repository.get_user_by_email(session, email=email)
        if (
            user is None
            or user.status != "active"
            or not verify_password(password, user.password_hash)
        ):
            raise AuthenticationError("invalid credentials")
        result = await session.execute(
            select(Membership).where(Membership.user_id == user.id, Membership.status == "active")
        )
        memberships = list(result.scalars())
        if not memberships:
            raise AuthenticationError("user has no active tenant membership")
        return user, memberships

    async def context_for_token(
        self, session: AsyncSession, *, token: str, tenant_id: str, settings: Settings
    ) -> TenantContext:
        user_id = decode_token(token, settings)
        found = await self.repository.get_user_for_tenant(
            session, tenant_id=tenant_id, user_id=user_id
        )
        if found is None:
            raise AuthenticationError("tenant membership not found")
        user, membership, tenant = found
        if user.status != "active" or membership.status != "active" or tenant.status != "active":
            raise AuthenticationError("inactive identity")
        return TenantContext(user_id=user.id, tenant_id=tenant.id, role=Role(membership.role))
