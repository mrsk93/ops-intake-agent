from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.artifacts.schemas import ArtifactUploadResponse, ArtifactView
from apps.api.app.auth.dependencies import get_current_context, get_db_session
from packages.artifacts.service import ArtifactIngestionError, ArtifactIngestionService
from packages.domain.identity import TenantContext
from packages.domain.parsing import ParsedArtifact
from packages.parsing.service import parse_artifact
from packages.providers.ports import OcrProvider, StoragePort

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


def _view(artifact) -> ArtifactView:
    return ArtifactView.model_validate(artifact)


@router.post("", response_model=ArtifactUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_artifact(
    request: Request,
    file: UploadFile = File(...),
    intake_id: str | None = Form(default=None),
    external_request_reference: str | None = Form(default=None),
    context: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> ArtifactUploadResponse:
    async def chunks() -> AsyncIterator[bytes]:
        while chunk := await file.read(1024 * 1024):
            yield chunk

    service: ArtifactIngestionService = request.app.state.artifact_service
    try:
        result = await service.ingest(
            session,
            tenant_id=context.tenant_id,
            filename=file.filename or "unnamed",
            chunks=chunks(),
            declared_media_type=file.content_type,
            intake_id=intake_id,
            external_request_reference=external_request_reference,
        )
    except ArtifactIngestionError as exc:
        code_status = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if exc.code in {"ARTIFACT_SIZE_LIMIT", "INTAKE_SIZE_LIMIT"}
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=code_status, detail={"code": exc.code, "message": exc.message}
        ) from exc
    return ArtifactUploadResponse(
        artifact=_view(result.artifact),
        duplicate=result.duplicate,
        duplicate_of_artifact_id=result.duplicate_of_artifact_id,
    )


@router.get("", response_model=list[ArtifactView])
async def list_artifacts(
    session: AsyncSession = Depends(get_db_session),
    context: TenantContext = Depends(get_current_context),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[ArtifactView]:
    artifacts = await request_repository().list_for_tenant(
        session, tenant_id=context.tenant_id, limit=limit
    )
    return [_view(artifact) for artifact in artifacts]


@router.get("/{artifact_id}", response_model=ArtifactView)
async def get_artifact(
    artifact_id: str,
    session: AsyncSession = Depends(get_db_session),
    context: TenantContext = Depends(get_current_context),
) -> ArtifactView:
    artifact = await request_repository().get(
        session, tenant_id=context.tenant_id, artifact_id=artifact_id
    )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return _view(artifact)


@router.get("/{artifact_id}/download")
async def download_artifact(
    artifact_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    context: TenantContext = Depends(get_current_context),
) -> Response:
    artifact = await _get_accepted_artifact(session, context, artifact_id)
    storage: StoragePort = request.app.state.storage_provider
    content = await storage.get(tenant_id=context.tenant_id, key=artifact.storage_key)
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.display_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{artifact_id}/view")
async def view_artifact(
    artifact_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    context: TenantContext = Depends(get_current_context),
) -> Response:
    artifact = await _get_accepted_artifact(session, context, artifact_id)
    storage: StoragePort = request.app.state.storage_provider
    content = await storage.get(tenant_id=context.tenant_id, key=artifact.storage_key)
    safe_media_type = (
        "text/plain" if artifact.detected_type == "email" else artifact.declared_media_type
    )
    return Response(
        content=content,
        media_type=safe_media_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{artifact.display_filename}"',
            "Content-Security-Policy": "default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{artifact_id}/parse", response_model=ParsedArtifact)
async def parse_uploaded_artifact(
    artifact_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    context: TenantContext = Depends(get_current_context),
) -> ParsedArtifact:
    artifact = await _get_accepted_artifact(session, context, artifact_id)
    storage: StoragePort = request.app.state.storage_provider
    ocr_provider: OcrProvider = request.app.state.ocr_provider
    content = await storage.get(tenant_id=context.tenant_id, key=artifact.storage_key)
    try:
        return await parse_artifact(
            artifact_id=artifact.id,
            tenant_id=context.tenant_id,
            artifact_type=artifact.detected_type,
            content=content,
            limits=request.app.state.artifact_limits,
            ocr_provider=ocr_provider,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


async def _get_accepted_artifact(session, context: TenantContext, artifact_id: str):
    artifact = await request_repository().get(
        session, tenant_id=context.tenant_id, artifact_id=artifact_id
    )
    if artifact is None or artifact.status != "accepted" or not artifact.storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return artifact


def request_repository():
    from packages.db.repositories import ArtifactRepository

    return ArtifactRepository()
