from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from redis.asyncio import Redis

from apps.api.app.artifacts.routes import router as artifacts_router
from apps.api.app.auth.dependencies import get_current_context, get_db_session, require_roles
from apps.api.app.auth.schemas import IdentityView, LoginRequest, LoginResponse, MembershipView
from apps.api.app.auth.service import AuthenticationError, AuthService, issue_token
from apps.api.app.config.settings import Settings, get_settings
from apps.api.app.db.session import create_session_factory
from apps.api.app.health.routes import router as health_router
from apps.api.app.intakes.routes import router as intakes_router
from packages.artifacts.service import ArtifactIngestionService
from packages.domain.artifacts import ArtifactLimits
from packages.domain.identity import Role, TenantContext
from packages.providers.ports import OcrProvider, StoragePort
from packages.providers.storage import LocalFileStorage, S3Storage
from packages.testkit.fakes import FakeOcrProvider, FakeStorage


def create_app(
    settings: Settings | None = None,
    *,
    session_factory: Any | None = None,
    storage_provider: StoragePort | None = None,
    ocr_provider: OcrProvider | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_session_factory, engine = (
        create_session_factory(resolved_settings)
        if session_factory is None
        else (session_factory, None)
    )
    redis_client = Redis.from_url(resolved_settings.redis_url, decode_responses=True)
    resolved_storage = storage_provider or _storage_for_settings(resolved_settings)
    resolved_ocr = ocr_provider or _ocr_for_settings(resolved_settings)
    artifact_limits = ArtifactLimits(
        max_artifacts_per_intake=resolved_settings.max_artifacts_per_intake,
        max_artifact_bytes=resolved_settings.max_artifact_bytes,
        max_total_intake_bytes=resolved_settings.max_total_intake_bytes,
        max_pdf_pages=resolved_settings.max_pdf_pages,
        max_workbook_sheets=resolved_settings.max_workbook_sheets,
        max_table_rows=resolved_settings.max_table_rows,
        max_extracted_text_chars=resolved_settings.max_extracted_text_chars,
    )

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
    app.state.storage_provider = resolved_storage
    app.state.ocr_provider = resolved_ocr
    app.state.artifact_limits = artifact_limits
    app.state.artifact_service = ArtifactIngestionService(
        resolved_storage,
        limits=artifact_limits,
        retention_days=resolved_settings.artifact_retention_days,
    )
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
    app.include_router(artifacts_router)
    app.include_router(intakes_router)
    return app


def _storage_for_settings(settings: Settings) -> StoragePort:
    if settings.artifact_storage_provider == "fake":
        return FakeStorage()
    if settings.artifact_storage_provider == "s3":
        return S3Storage(
            endpoint=settings.object_storage_endpoint,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            bucket=settings.object_storage_bucket,
        )
    return LocalFileStorage(settings.artifact_storage_root)


class _UnavailableOcrProvider:
    async def recognize(
        self, *, tenant_id: str, artifact_id: str, content: bytes
    ) -> dict[str, str]:
        del tenant_id, artifact_id, content
        raise RuntimeError("OCR provider is not configured")


def _ocr_for_settings(settings: Settings) -> OcrProvider:
    return FakeOcrProvider() if settings.ocr_provider == "fake" else _UnavailableOcrProvider()


app = create_app()
