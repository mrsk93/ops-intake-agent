from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from redis.asyncio import Redis

from apps.api.app.auth.dependencies import get_current_context, get_db_session, require_roles
from apps.api.app.auth.schemas import IdentityView, LoginRequest, LoginResponse, MembershipView
from apps.api.app.auth.service import AuthenticationError, AuthService, issue_token
from apps.api.app.config.settings import Settings, get_settings
from apps.api.app.db.session import create_session_factory
from apps.api.app.health.routes import router as health_router
from packages.domain.identity import Role, TenantContext


def create_app(settings: Settings | None = None, *, session_factory: Any | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_session_factory, engine = (
        create_session_factory(resolved_settings)
        if session_factory is None
        else (session_factory, None)
    )
    redis_client = Redis.from_url(resolved_settings.redis_url, decode_responses=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await redis_client.aclose()
        if engine is not None:
            await engine.dispose()

    app = FastAPI(title="Ops Intake Agent API", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.session_factory = resolved_session_factory
    app.state.redis_client = redis_client
    app.include_router(health_router)

    auth_router = APIRouter(prefix="/api/auth", tags=["auth"])

    @auth_router.post("/login", response_model=LoginResponse)
    async def login(
        payload: LoginRequest, request: Request, session=Depends(get_db_session)
    ) -> LoginResponse:
        try:
            user, memberships = await AuthService().login(
                session,
                email=payload.email,
                password=payload.password,
                settings=request.app.state.settings,
            )
        except AuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
            ) from exc
        return LoginResponse(
            access_token=issue_token(user_id=user.id, settings=request.app.state.settings),
            memberships=[
                MembershipView(tenant_id=item.tenant_id, role=item.role) for item in memberships
            ],
        )

    @auth_router.get("/me", response_model=IdentityView)
    async def me(
        context: TenantContext = Depends(get_current_context), session=Depends(get_db_session)
    ) -> IdentityView:
        user, _, _ = await AuthService().repository.get_user_for_tenant(
            session, tenant_id=context.tenant_id, user_id=context.user_id
        )
        return IdentityView(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            tenant_id=context.tenant_id,
            role=context.role.value,
        )

    app.include_router(auth_router)

    access_router = APIRouter(prefix="/api", tags=["access"])

    @access_router.get("/viewer/ping")
    async def viewer_ping(context: TenantContext = Depends(get_current_context)) -> dict[str, str]:
        return {"status": "ok", "tenant_id": context.tenant_id, "role": context.role.value}

    @access_router.get("/reviewer/ping")
    async def reviewer_ping(
        context: TenantContext = Depends(require_roles(Role.REVIEWER, Role.ADMIN)),
    ) -> dict[str, str]:
        return {"status": "ok", "tenant_id": context.tenant_id, "role": context.role.value}

    @access_router.get("/admin/ping")
    async def admin_ping(
        context: TenantContext = Depends(require_roles(Role.ADMIN)),
    ) -> dict[str, str]:
        return {"status": "ok", "tenant_id": context.tenant_id, "role": context.role.value}

    app.include_router(access_router)
    return app


app = create_app()
