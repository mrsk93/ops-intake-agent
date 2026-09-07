from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import (
    Approval,
    AuditEvent,
    ExecutionAttempt,
    IntakeRun,
    ProposedAction,
    RemoteReceipt,
    Review,
)
from packages.db.repositories import OperationsRepository, ReviewRepository
from packages.domain.canonical import DraftFulfillmentRequest, payload_sha256
from packages.domain.master_data import synthetic_master_data
from packages.domain.validation import validate_request
from packages.providers.ports import OperationsPort


class OperationsError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OperationsService:
    def __init__(
        self,
        operations: OperationsPort,
        *,
        review_repository: ReviewRepository | None = None,
        repository: OperationsRepository | None = None,
    ) -> None:
        self.operations = operations
        self.review_repository = review_repository or ReviewRepository()
        self.repository = repository or OperationsRepository()

    async def approve_and_execute(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        intake_run_id: str,
        actor_user_id: str,
        expected_review_version: int,
        proposed_action_id: str,
        preview_payload_sha256: str,
    ) -> dict[str, Any]:
        action, review, intake = await self._load_current(
            session,
            tenant_id=tenant_id,
            intake_run_id=intake_run_id,
            action_id=proposed_action_id,
        )
        self._guard_approval(
            action=action,
            review=review,
            intake=intake,
            expected_review_version=expected_review_version,
            preview_payload_sha256=preview_payload_sha256,
        )
        await self._revalidate_current(session, tenant_id=tenant_id, action=action, intake=intake)
        approval = Approval(
            id=f"approval-{uuid4().hex}",
            tenant_id=tenant_id,
            proposed_action_id=action.id,
            review_id=review.id,
            actor_user_id=actor_user_id,
            review_version=expected_review_version,
            preview_payload_sha256=preview_payload_sha256,
            status="active",
            created_at=datetime.now(UTC),
        )
        action.status = "claimed"
        action.approval_id = approval.id
        action.claimed_at = datetime.now(UTC)
        session.add(approval)
        await _add_audit(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="approve_action",
            entity_type="proposed_action",
            entity_id=action.id,
            details={
                "approval_id": approval.id,
                "review_version": expected_review_version,
                "payload_sha256": action.payload_sha256,
            },
        )
        await session.commit()
        return await self._execute(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action_id=action.id,
            approval_id=approval.id,
            intake_run_id=intake_run_id,
        )

    async def recover(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        intake_run_id: str,
        actor_user_id: str,
        reason: str,
    ) -> dict[str, Any]:
        action = await self._action_for_intake(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        if action is None:
            raise OperationsError("ACTION_NOT_FOUND", "execution action not found")
        if action.status == "verified":
            return await self.execution_status(
                session, tenant_id=tenant_id, intake_run_id=intake_run_id
            )
        if action.status not in {"uncertain", "executing"} or not action.approval_id:
            raise OperationsError(
                "RECOVERY_NOT_ALLOWED", "only uncertain or executing approved actions can recover"
            )
        await _add_audit(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="recover_execution",
            entity_type="proposed_action",
            entity_id=action.id,
            details={"reason": reason.strip()[:500]},
        )
        await session.commit()
        return await self._resolve_uncertain(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            approval_id=action.approval_id,
            intake_run_id=intake_run_id,
        )

    async def execution_status(
        self, session: AsyncSession, *, tenant_id: str, intake_run_id: str
    ) -> dict[str, Any]:
        action = await self._action_for_intake(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        if action is None:
            raise OperationsError("ACTION_NOT_FOUND", "execution action not found")
        attempts = await self.repository.list_attempts(
            session, tenant_id=tenant_id, action_id=action.id
        )
        receipt = await self.repository.get_receipt(
            session, tenant_id=tenant_id, action_id=action.id
        )
        audit = await self.repository.list_audit(session, tenant_id=tenant_id, entity_id=action.id)
        return {
            "action_id": action.id,
            "status": action.status,
            "idempotency_key_short": action.idempotency_key[:12],
            "approval_id": action.approval_id,
            "attempts": len(attempts),
            "timeline": [
                {
                    "attempt_no": item.attempt_no,
                    "status": item.status,
                    "error_code": item.error_code,
                    "started_at": item.started_at.isoformat(),
                    "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                }
                for item in attempts
            ],
            "receipt": (
                {
                    "remote_id": receipt.remote_id,
                    "payload_sha256": receipt.payload_sha256,
                    "verified": receipt.verified,
                    "created_at": receipt.created_at.isoformat(),
                }
                if receipt
                else None
            ),
            "audit": [
                {
                    "action": item.action,
                    "entity_type": item.entity_type,
                    "details": json.loads(item.details_json),
                    "created_at": item.created_at.isoformat(),
                }
                for item in audit
            ],
        }

    async def _execute(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        actor_user_id: str,
        action_id: str,
        approval_id: str,
        intake_run_id: str,
    ) -> dict[str, Any]:
        action = await self.review_repository.get_action(
            session, tenant_id=tenant_id, action_id=action_id
        )
        if action is None:
            raise OperationsError("ACTION_NOT_FOUND", "execution action not found")
        attempt = await self._start_attempt(
            session, tenant_id=tenant_id, action=action, attempt_no=1
        )
        try:
            response = await self.operations.create_draft(
                tenant_id=tenant_id,
                idempotency_key=action.idempotency_key,
                payload=json.loads(action.payload_json),
                correlation_id=attempt.id,
            )
        except TimeoutError:
            attempt.status = "uncertain"
            attempt.error_code = "OPS_TIMEOUT"
            attempt.completed_at = datetime.now(UTC)
            action.status = "uncertain"
            await session.commit()
            return await self._resolve_uncertain(
                session,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action=action,
                approval_id=approval_id,
                intake_run_id=intake_run_id,
            )
        except Exception as exc:
            attempt.status = "failed"
            attempt.error_code = "OPS_CREATE_FAILED"
            attempt.completed_at = datetime.now(UTC)
            action.status = "failed"
            await session.commit()
            raise OperationsError("OPS_CREATE_FAILED", "operations provider create failed") from exc
        return await self._verify_response(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            approval_id=approval_id,
            intake_run_id=intake_run_id,
            attempt=attempt,
            response=response,
        )

    async def _resolve_uncertain(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        actor_user_id: str,
        action: ProposedAction,
        approval_id: str,
        intake_run_id: str,
    ) -> dict[str, Any]:
        found = await self.operations.lookup(
            tenant_id=tenant_id, idempotency_key=action.idempotency_key
        )
        if found is not None:
            attempts = await self.repository.list_attempts(
                session, tenant_id=tenant_id, action_id=action.id
            )
            return await self._verify_response(
                session,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                action=action,
                approval_id=approval_id,
                intake_run_id=intake_run_id,
                attempt=attempts[-1],
                response=found,
            )
        attempts = await self.repository.list_attempts(
            session, tenant_id=tenant_id, action_id=action.id
        )
        retry = await self._start_attempt(
            session, tenant_id=tenant_id, action=action, attempt_no=len(attempts) + 1
        )
        try:
            response = await self.operations.create_draft(
                tenant_id=tenant_id,
                idempotency_key=action.idempotency_key,
                payload=json.loads(action.payload_json),
                correlation_id=retry.id,
            )
        except TimeoutError as exc:
            retry.status = "uncertain"
            retry.error_code = "OPS_TIMEOUT"
            retry.completed_at = datetime.now(UTC)
            action.status = "uncertain"
            await session.commit()
            raise OperationsError(
                "EXECUTION_UNCERTAIN", "remote execution remains uncertain"
            ) from exc
        return await self._verify_response(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            approval_id=approval_id,
            intake_run_id=intake_run_id,
            attempt=retry,
            response=response,
        )

    async def _verify_response(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        actor_user_id: str,
        action: ProposedAction,
        approval_id: str,
        intake_run_id: str,
        attempt: ExecutionAttempt,
        response: Any,
    ) -> dict[str, Any]:
        if not isinstance(response, dict):
            return await self._mismatch(
                session, action=action, attempt=attempt, code="RECEIPT_INVALID"
            )
        remote_id = response.get("remote_id")
        if (
            response.get("tenant_id") != tenant_id
            or response.get("idempotency_key") != action.idempotency_key
            or not isinstance(remote_id, str)
            or (
                "payload_sha256" in response
                and response.get("payload_sha256") != action.payload_sha256
            )
        ):
            return await self._mismatch(
                session, action=action, attempt=attempt, code="RECEIPT_MISMATCH"
            )
        try:
            readback = await self.operations.read_back(tenant_id=tenant_id, remote_id=remote_id)
        except TimeoutError as exc:
            return await self._readback_uncertain(
                session, action=action, attempt=attempt, code="OPS_READBACK_TIMEOUT", cause=exc
            )
        except Exception as exc:
            return await self._readback_uncertain(
                session, action=action, attempt=attempt, code="OPS_READBACK_FAILED", cause=exc
            )
        if (
            not isinstance(readback, dict)
            or readback.get("tenant_id") != tenant_id
            or readback.get("idempotency_key") != action.idempotency_key
            or readback.get("payload_sha256") != action.payload_sha256
        ):
            return await self._mismatch(
                session, action=action, attempt=attempt, code="RECEIPT_MISMATCH"
            )
        safe_receipt = {
            "tenant_id": tenant_id,
            "idempotency_key": action.idempotency_key,
            "remote_id": remote_id,
            "payload_sha256": action.payload_sha256,
        }
        receipt = RemoteReceipt(
            id=f"receipt-{uuid4().hex}",
            tenant_id=tenant_id,
            proposed_action_id=action.id,
            execution_attempt_id=attempt.id,
            remote_id=remote_id,
            payload_sha256=action.payload_sha256,
            receipt_json=json.dumps(safe_receipt, sort_keys=True),
            verified=True,
            created_at=datetime.now(UTC),
        )
        attempt.status = "verified"
        attempt.response_json = json.dumps(safe_receipt, sort_keys=True)
        attempt.completed_at = datetime.now(UTC)
        action.status = "verified"
        approval = await self.repository.get_approval(
            session, tenant_id=tenant_id, approval_id=approval_id
        )
        if approval:
            approval.status = "consumed"
            approval.consumed_at = datetime.now(UTC)
        review = await self.review_repository.get(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        if review:
            review.status = "approved"
        intake = await self.review_repository.get_intake(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        if intake:
            intake.status = "completed"
            intake.completed_at = datetime.now(UTC)
        session.add(receipt)
        await _add_audit(
            session,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action="verify_execution",
            entity_type="proposed_action",
            entity_id=action.id,
            details={"remote_id": remote_id, "payload_sha256": action.payload_sha256},
        )
        await session.commit()
        return await self.execution_status(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )

    async def _mismatch(
        self,
        session: AsyncSession,
        *,
        action: ProposedAction,
        attempt: ExecutionAttempt,
        code: str,
    ) -> dict[str, Any]:
        attempt.status = "manual_exception"
        attempt.error_code = code
        attempt.completed_at = datetime.now(UTC)
        action.status = "manual_exception"
        await _add_audit(
            session,
            tenant_id=action.tenant_id,
            actor_user_id=None,
            action="execution_manual_exception",
            entity_type="proposed_action",
            entity_id=action.id,
            details={"error_code": code, "attempt_id": attempt.id},
        )
        await session.commit()
        raise OperationsError(code, "remote receipt did not match the approved payload")

    async def _readback_uncertain(
        self,
        session: AsyncSession,
        *,
        action: ProposedAction,
        attempt: ExecutionAttempt,
        code: str,
        cause: Exception,
    ) -> dict[str, Any]:
        attempt.status = "uncertain"
        attempt.error_code = code
        attempt.completed_at = datetime.now(UTC)
        action.status = "uncertain"
        await session.commit()
        raise OperationsError(
            "EXECUTION_UNCERTAIN", "remote result could not be read back safely"
        ) from cause

    async def _start_attempt(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        action: ProposedAction,
        attempt_no: int,
    ) -> ExecutionAttempt:
        attempt = ExecutionAttempt(
            id=f"attempt-{uuid4().hex}",
            tenant_id=tenant_id,
            proposed_action_id=action.id,
            attempt_no=attempt_no,
            idempotency_key=action.idempotency_key,
            status="executing",
            started_at=datetime.now(UTC),
        )
        action.status = "executing"
        session.add(attempt)
        await session.commit()
        return attempt

    async def _load_current(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        intake_run_id: str,
        action_id: str,
    ) -> tuple[ProposedAction, Review, IntakeRun]:
        action = await self.review_repository.get_action(
            session, tenant_id=tenant_id, action_id=action_id
        )
        review = await self.review_repository.get(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        intake = await self.review_repository.get_intake(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        if (
            action is None
            or review is None
            or intake is None
            or action.intake_run_id != intake_run_id
        ):
            raise OperationsError("ACTION_NOT_FOUND", "approved action not found")
        return action, review, intake

    async def _action_for_intake(
        self, session: AsyncSession, *, tenant_id: str, intake_run_id: str
    ) -> ProposedAction | None:
        result = await session.execute(
            select(ProposedAction)
            .where(
                ProposedAction.tenant_id == tenant_id,
                ProposedAction.intake_run_id == intake_run_id,
            )
            .order_by(ProposedAction.created_at.desc())
        )
        return result.scalars().first()

    @staticmethod
    def _guard_approval(
        *,
        action: ProposedAction,
        review: Review,
        intake: IntakeRun,
        expected_review_version: int,
        preview_payload_sha256: str,
    ) -> None:
        if (
            review.current_version != expected_review_version
            or action.review_version != expected_review_version
        ):
            raise OperationsError("STALE_REVIEW_VERSION", "refresh before approving this action")
        if action.status == "verified":
            raise OperationsError("ALREADY_EXECUTED", "this action has already succeeded")
        if action.status != "ready":
            raise OperationsError("STALE_ACTION", "only the current ready preview can be approved")
        if action.payload_sha256 != preview_payload_sha256:
            raise OperationsError("PREVIEW_HASH_MISMATCH", "approval is not bound to this preview")
        if review.current_draft_version_id != action.draft_version_id:
            raise OperationsError("STALE_ACTION", "the draft changed after this preview")
        if review.current_validation_snapshot_id != action.validation_snapshot_id:
            raise OperationsError("VALIDATION_STALE", "validation changed after this preview")
        if intake.status not in {"review_required", "review_received"}:
            raise OperationsError("INTAKE_NOT_REVIEWABLE", "intake is not in a reviewable state")

    async def _revalidate_current(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        action: ProposedAction,
        intake: IntakeRun,
    ) -> None:
        payload = DraftFulfillmentRequest.model_validate(json.loads(action.payload_json))
        if payload_sha256(payload) != action.payload_sha256:
            raise OperationsError("PREVIEW_HASH_MISMATCH", "stored preview payload hash is invalid")
        report = validate_request(
            payload,
            master_data=synthetic_master_data(tenant_id),
            received_at=intake.started_at,
        )
        if report.blocking:
            raise OperationsError(
                "REVALIDATION_BLOCKED", "current deterministic validation blocks execution"
            )
        review_issues = await self.review_repository.list_issues(
            session,
            tenant_id=tenant_id,
            snapshot_id=action.validation_snapshot_id,
        )
        review = await self.review_repository.get(
            session, tenant_id=tenant_id, intake_run_id=intake.id
        )
        acknowledged = set(json.loads(review.acknowledged_warnings_json)) if review else set()
        if any(
            item.severity == "warning" and item.code not in acknowledged for item in review_issues
        ):
            raise OperationsError("WARNINGS_NOT_ACKNOWLEDGED", "all warnings must be acknowledged")


async def _add_audit(
    session: AsyncSession,
    *,
    tenant_id: str,
    actor_user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any],
) -> None:
    session.add(
        AuditEvent(
            id=f"audit-{uuid4().hex}",
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            correlation_id=f"corr-{uuid4().hex}",
            details_json=json.dumps(details, sort_keys=True),
            created_at=datetime.now(UTC),
        )
    )
