from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

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
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.auth.dependencies import get_current_context, get_db_session, require_roles
from apps.api.app.intakes.schemas import (
    ApproveRequest,
    EditFieldsRequest,
    IntakeCreate,
    IntakeView,
    PreviewRequest,
    RecoverRequest,
    RevalidateRequest,
    WarningAcknowledgementRequest,
)
from packages.db.models import IntakeRun
from packages.db.repositories import ArtifactRepository, IntakeRunRepository
from packages.domain.identity import Role, TenantContext
from packages.domain.review import ReviewFixture
from packages.operations.service import OperationsError, OperationsService
from packages.review.service import ReviewError, ReviewService

router = APIRouter(prefix="/api/intakes", tags=["intakes"])
reviewer = Depends(require_roles(Role.REVIEWER, Role.ADMIN))


@router.post("", response_model=IntakeView, status_code=status.HTTP_201_CREATED)
async def create_intake(
    payload: IntakeCreate,
    context: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> IntakeView:
    now = datetime.now(UTC)
    intake = IntakeRun(
        id=f"intake-{uuid4().hex}",
        tenant_id=context.tenant_id,
        source_channel=payload.source_channel,
        demo_fixture=payload.fixture,
        status="received",
        graph_thread_id=f"intake-{uuid4().hex}",
        external_request_reference=payload.external_request_reference,
        review_version=1,
        started_at=now,
    )
    await IntakeRunRepository().create(session, intake_run=intake)
    return IntakeView.model_validate(intake)


@router.get("", response_model=list[IntakeView])
async def list_intakes(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=100),
    context: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[IntakeView]:
    items = await IntakeRunRepository().list_for_tenant(
        session, tenant_id=context.tenant_id, limit=limit
    )
    if status_filter:
        items = [item for item in items if item.status == status_filter]
    return [IntakeView.model_validate(item) for item in items]


@router.get("/{intake_id}", response_model=IntakeView)
async def get_intake(
    intake_id: str,
    context: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> IntakeView:
    intake = await _get_intake(session, context, intake_id)
    return IntakeView.model_validate(intake)


@router.post("/{intake_id}/artifacts", status_code=status.HTTP_201_CREATED)
async def upload_intake_artifact(
    intake_id: str,
    request: Request,
    file: UploadFile = File(...),
    external_request_reference: str | None = Form(default=None),
    context: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _get_intake(session, context, intake_id)

    async def chunks() -> AsyncIterator[bytes]:
        while chunk := await file.read(1024 * 1024):
            yield chunk

    try:
        result = await request.app.state.artifact_service.ingest(
            session,
            tenant_id=context.tenant_id,
            filename=file.filename or "unnamed",
            chunks=chunks(),
            declared_media_type=file.content_type,
            intake_id=intake_id,
            external_request_reference=external_request_reference,
        )
    except ValueError as exc:
        code = getattr(exc, "code", "ARTIFACT_REJECTED")
        message = getattr(exc, "message", "artifact rejected")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": code, "message": message},
        ) from exc
    artifact = result.artifact
    return {
        "artifact": {
            "id": artifact.id,
            "display_filename": artifact.display_filename,
            "status": artifact.status,
            "content_sha256": artifact.content_sha256,
            "size_bytes": artifact.size_bytes,
        },
        "duplicate": result.duplicate,
    }


@router.post("/{intake_id}/submit", response_model=IntakeView)
async def submit_intake(
    intake_id: str,
    session: AsyncSession = Depends(get_db_session),
    context: TenantContext = Depends(get_current_context),
) -> IntakeView:
    intake = await _get_intake(session, context, intake_id)
    artifact_ids = [f"demo-artifact-{intake_id}"]
    artifacts = await ArtifactRepository().list_for_tenant(
        session, tenant_id=context.tenant_id, limit=100
    )
    accepted = [
        item.id for item in artifacts if item.intake_id == intake_id and item.status == "accepted"
    ]
    if accepted:
        artifact_ids = accepted
    await ReviewService().ensure_demo_review(
        session,
        tenant_id=context.tenant_id,
        intake_run_id=intake_id,
        actor_user_id=context.user_id,
        fixture=cast(ReviewFixture, intake.demo_fixture),
        source_artifact_ids=artifact_ids,
    )
    return IntakeView.model_validate(intake)


@router.get("/{intake_id}/review")
async def get_review(
    intake_id: str,
    context: TenantContext = reviewer,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _get_intake(session, context, intake_id)
    return await _handle_review_error(
        lambda: ReviewService().get_review(
            session, tenant_id=context.tenant_id, intake_run_id=intake_id
        )
    )


@router.patch("/{intake_id}/review/fields")
async def edit_review_fields(
    intake_id: str,
    payload: EditFieldsRequest,
    context: TenantContext = reviewer,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _get_intake(session, context, intake_id)
    return await _handle_review_error(
        lambda: ReviewService().edit_fields(
            session,
            tenant_id=context.tenant_id,
            intake_run_id=intake_id,
            actor_user_id=context.user_id,
            expected_review_version=payload.expected_review_version,
            edits=[item.model_dump(mode="json") for item in payload.edits],
        )
    )


@router.post("/{intake_id}/review/acknowledge-warning")
async def acknowledge_warning(
    intake_id: str,
    payload: WarningAcknowledgementRequest,
    context: TenantContext = reviewer,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _get_intake(session, context, intake_id)
    return await _handle_review_error(
        lambda: ReviewService().acknowledge_warning(
            session,
            tenant_id=context.tenant_id,
            intake_run_id=intake_id,
            expected_review_version=payload.expected_review_version,
            warning_code=payload.warning_code,
        )
    )


@router.post("/{intake_id}/review/revalidate")
async def revalidate_review(
    intake_id: str,
    payload: RevalidateRequest,
    context: TenantContext = reviewer,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _get_intake(session, context, intake_id)
    return await _handle_review_error(
        lambda: ReviewService().revalidate(
            session,
            tenant_id=context.tenant_id,
            intake_run_id=intake_id,
            actor_user_id=context.user_id,
            expected_review_version=payload.expected_review_version,
        )
    )


@router.post("/{intake_id}/preview", status_code=status.HTTP_201_CREATED)
async def create_action_preview(
    intake_id: str,
    payload: PreviewRequest,
    context: TenantContext = reviewer,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _get_intake(session, context, intake_id)
    return await _handle_review_error(
        lambda: ReviewService().build_preview(
            session,
            tenant_id=context.tenant_id,
            intake_run_id=intake_id,
            expected_review_version=payload.expected_review_version,
        )
    )


@router.post("/{intake_id}/approve")
async def approve_action(
    intake_id: str,
    payload: ApproveRequest,
    request: Request,
    context: TenantContext = reviewer,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _get_intake(session, context, intake_id)
    try:
        return await OperationsService(request.app.state.operations_provider).approve_and_execute(
            session,
            tenant_id=context.tenant_id,
            intake_run_id=intake_id,
            actor_user_id=context.user_id,
            expected_review_version=payload.expected_review_version,
            proposed_action_id=payload.proposed_action_id,
            preview_payload_sha256=payload.preview_payload_sha256,
        )
    except OperationsError as exc:
        raise _operations_http_error(exc) from exc


@router.get("/{intake_id}/execution")
async def get_execution(
    intake_id: str,
    request: Request,
    context: TenantContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _get_intake(session, context, intake_id)
    try:
        return await OperationsService(request.app.state.operations_provider).execution_status(
            session, tenant_id=context.tenant_id, intake_run_id=intake_id
        )
    except OperationsError as exc:
        raise _operations_http_error(exc) from exc


@router.post("/{intake_id}/execution/recover")
async def recover_execution(
    intake_id: str,
    payload: RecoverRequest,
    request: Request,
    context: TenantContext = reviewer,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _get_intake(session, context, intake_id)
    try:
        return await OperationsService(request.app.state.operations_provider).recover(
            session,
            tenant_id=context.tenant_id,
            intake_run_id=intake_id,
            actor_user_id=context.user_id,
            reason=payload.reason,
        )
    except OperationsError as exc:
        raise _operations_http_error(exc) from exc


@router.get("/{intake_id}/audit")
async def get_audit(
    intake_id: str,
    request: Request,
    context: TenantContext = reviewer,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await _get_intake(session, context, intake_id)
    try:
        execution = await OperationsService(request.app.state.operations_provider).execution_status(
            session, tenant_id=context.tenant_id, intake_run_id=intake_id
        )
    except OperationsError as exc:
        if exc.code != "ACTION_NOT_FOUND":
            raise _operations_http_error(exc) from exc
        execution = {"audit": []}
    review = await ReviewService().get_review(
        session, tenant_id=context.tenant_id, intake_run_id=intake_id
    )
    return {"events": [*review["audit"], *execution["audit"]]}


async def _get_intake(session: AsyncSession, context: TenantContext, intake_id: str) -> IntakeRun:
    intake = await IntakeRunRepository().get(
        session, tenant_id=context.tenant_id, intake_run_id=intake_id
    )
    if intake is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return intake


async def _handle_review_error(call):
    try:
        return await call()
    except ReviewError as exc:
        detail = {"code": exc.code, "message": exc.message}
        if exc.current_version is not None:
            detail["currentVersion"] = exc.current_version
        code_status = (
            status.HTTP_409_CONFLICT
            if exc.code == "STALE_REVIEW_VERSION"
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=code_status, detail=detail) from exc


def _operations_http_error(exc: OperationsError) -> HTTPException:
    code_status = (
        status.HTTP_409_CONFLICT
        if exc.code
        in {
            "STALE_REVIEW_VERSION",
            "STALE_ACTION",
            "PREVIEW_HASH_MISMATCH",
            "VALIDATION_STALE",
            "ALREADY_EXECUTED",
            "RECEIPT_MISMATCH",
            "EXECUTION_UNCERTAIN",
            "RECOVERY_NOT_ALLOWED",
        }
        else status.HTTP_422_UNPROCESSABLE_CONTENT
    )
    return HTTPException(status_code=code_status, detail={"code": exc.code, "message": exc.message})
