from collections.abc import Awaitable, Callable

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.auth.service import AuthenticationError, AuthService
from packages.domain.identity import Role, TenantContext


async def get_db_session(request: Request) -> AsyncSession:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()


async def get_current_context(
    request: Request,
    authorization: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> TenantContext:
    if not authorization or not authorization.lower().startswith("bearer ") or not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required"
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        return await AuthService().context_for_token(
            session, token=token, tenant_id=x_tenant_id, settings=request.app.state.settings
        )
    except AuthenticationError as exc:
        # Do not reveal whether a tenant, user or membership exists.
        if str(exc) == "tenant membership not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="resource not found"
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required"
        ) from exc


def require_roles(*allowed_roles: Role) -> Callable[..., Awaitable[TenantContext]]:
    async def dependency(context: TenantContext = Depends(get_current_context)) -> TenantContext:
        if context.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role")
        return context

    return dependency
