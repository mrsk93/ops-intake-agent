from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import (
    DraftVersion,
    IntakeRun,
    Review,
    ReviewEdit,
    ValidationIssueRecord,
    ValidationSnapshot,
)
from packages.db.repositories import IntakeRunRepository, ReviewRepository
from packages.domain.canonical import (
    DraftFulfillmentRequest,
    ValidationIssue,
    ValidationReport,
    payload_sha256,
)
from packages.domain.extraction import is_supported_field_path
from packages.domain.master_data import synthetic_master_data
from packages.domain.review import ReviewEvidence, ReviewField, ReviewFixture, ReviewRuleCitation
from packages.domain.validation import validate_request

RULES_FINGERPRINT = hashlib.sha256(b"synthetic-sop-harborline-v1").hexdigest()
DEMO_RULES = [
    ReviewRuleCitation(
        rule_ref="sop:harborline:fulfillment:1",
        title="Harborline fulfillment intake policy",
        version="1.0",
        effective_from="2026-01-01",
        safe_summary=(
            "Requests require an active customer, authorized origin, supported service level "
            "and complete line items."
        ),
    )
]


class ReviewError(ValueError):
    def __init__(self, code: str, message: str, *, current_version: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.current_version = current_version


class ReviewService:
    def __init__(
        self,
        *,
        repository: ReviewRepository | None = None,
        intake_repository: IntakeRunRepository | None = None,
    ) -> None:
        self.repository = repository or ReviewRepository()
        self.intake_repository = intake_repository or IntakeRunRepository()

    async def ensure_demo_review(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        intake_run_id: str,
        actor_user_id: str,
        fixture: ReviewFixture = "valid",
        source_artifact_ids: list[str] | None = None,
    ) -> Review:
        intake = await self.intake_repository.get(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        if intake is None:
            raise ReviewError("INTAKE_NOT_FOUND", "intake not found")
        existing = await self.repository.get(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        if existing is not None:
            return existing

        artifact_ids = source_artifact_ids or [f"demo-artifact-{intake_run_id}"]
        payload, fields = _demo_fixture(
            tenant_id=tenant_id,
            intake_run_id=intake_run_id,
            fixture=fixture,
            artifact_id=artifact_ids[0],
        )
        report = _review_report(
            payload,
            tenant_id=tenant_id,
            fixture=fixture,
            received_at=intake.started_at,
            fields=fields,
        )
        draft, snapshot, issues = _version_bundle(
            tenant_id=tenant_id,
            intake_run_id=intake_run_id,
            payload=payload,
            fields=fields,
            report=report,
            version=1,
            source="extraction",
            actor_user_id=actor_user_id,
            prior_version_id=None,
        )
        review = Review(
            id=f"review-{uuid4().hex}",
            tenant_id=tenant_id,
            intake_run_id=intake_run_id,
            current_version=1,
            status="open",
            acknowledged_warnings_json="[]",
            current_draft_version_id=draft.id,
            current_validation_snapshot_id=snapshot.id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        intake.status = "review_required"
        intake.review_version = 1
        await self.repository.save_review_bundle(
            session,
            review=review,
            draft=draft,
            snapshot=snapshot,
            issues=issues,
        )
        return review

    async def get_review(
        self, session: AsyncSession, *, tenant_id: str, intake_run_id: str
    ) -> dict[str, Any]:
        review = await self.repository.get(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        if review is None:
            raise ReviewError("REVIEW_NOT_FOUND", "review not found")
        draft = await self.repository.get_draft(
            session, tenant_id=tenant_id, draft_version_id=review.current_draft_version_id
        )
        snapshot = await self.repository.get_snapshot(
            session,
            tenant_id=tenant_id,
            snapshot_id=review.current_validation_snapshot_id,
        )
        if draft is None or snapshot is None:
            raise ReviewError("REVIEW_STATE_INCOMPLETE", "review state is incomplete")
        issues = await self.repository.list_issues(
            session, tenant_id=tenant_id, snapshot_id=snapshot.id
        )
        edits = await self.repository.list_edits(session, tenant_id=tenant_id, review_id=review.id)
        fields = [ReviewField.model_validate(item) for item in json.loads(draft.fields_json)]
        return {
            "intake_run_id": intake_run_id,
            "review_version": review.current_version,
            "status": review.status,
            "draft_version_id": draft.id,
            "draft": {
                "fields": [item.model_dump(mode="json") for item in fields],
                "payload": json.loads(draft.payload_json),
                "payload_sha256": draft.payload_sha256,
            },
            "issues": [_issue_view(issue) for issue in issues],
            "rules": [item.model_dump(mode="json") for item in DEMO_RULES],
            "acknowledged_warnings": json.loads(review.acknowledged_warnings_json),
            "preview": None,
            "audit": [
                {
                    "kind": "field_edit",
                    "field_path": item.field_path,
                    "reason": item.reason,
                    "actor_user_id": item.actor_user_id,
                    "created_at": item.created_at.isoformat(),
                }
                for item in edits
            ],
        }

    async def edit_fields(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        intake_run_id: str,
        actor_user_id: str,
        expected_review_version: int,
        edits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        review, draft, intake = await self._current_records(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        self._check_version(review, expected_review_version)
        if not edits:
            raise ReviewError("NO_EDITS", "at least one field edit is required")
        payload = json.loads(draft.payload_json)
        fields = [ReviewField.model_validate(item) for item in json.loads(draft.fields_json)]
        fields_by_path = {field.path: field for field in fields}
        review_edits: list[ReviewEdit] = []
        for edit in edits:
            path = edit.get("path")
            reason = edit.get("reason")
            evidence_ids = edit.get("evidence_ref_ids")
            if not isinstance(path, str) or not is_supported_field_path(path):
                raise ReviewError("UNSUPPORTED_FIELD_PATH", "field path is not editable")
            if not isinstance(reason, str) or not reason.strip():
                raise ReviewError("EDIT_REASON_REQUIRED", "each edit requires a reason")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise ReviewError("EDIT_EVIDENCE_REQUIRED", "each edit requires evidence")
            field = fields_by_path.get(path)
            if field is None or any(
                ref_id not in {item.ref_id for item in field.evidence} for ref_id in evidence_ids
            ):
                raise ReviewError(
                    "EDIT_EVIDENCE_NOT_FOUND", "edit evidence is not attached to this field"
                )
            before = _get_path(payload, path)
            _set_path(payload, path, edit.get("value"))
            review_edits.append(
                ReviewEdit(
                    id=f"edit-{uuid4().hex}",
                    tenant_id=tenant_id,
                    review_id=review.id,
                    draft_version_id="pending",
                    field_path=path,
                    before_json=json.dumps(before, sort_keys=True, default=str),
                    after_json=json.dumps(edit.get("value"), sort_keys=True, default=str),
                    reason=reason.strip()[:500],
                    actor_user_id=actor_user_id,
                    created_at=datetime.now(UTC),
                )
            )
        try:
            normalized = DraftFulfillmentRequest.model_validate(payload)
        except Exception as exc:
            raise ReviewError(
                "DRAFT_INVALID", "edit does not produce a valid canonical draft"
            ) from exc
        next_version = await self.repository.next_draft_version(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        updated_fields = _edited_fields(
            fields, edits=edits, normalized_payload=normalized.model_dump(mode="json")
        )
        report = _review_report(
            normalized,
            tenant_id=tenant_id,
            fixture="valid",
            received_at=intake.started_at,
            fields=updated_fields,
        )
        new_draft, snapshot, issues = _version_bundle(
            tenant_id=tenant_id,
            intake_run_id=intake_run_id,
            payload=normalized,
            fields=updated_fields,
            report=report,
            version=next_version,
            source="operator_edit",
            actor_user_id=actor_user_id,
            prior_version_id=draft.id,
        )
        for edit in review_edits:
            edit.draft_version_id = new_draft.id
        review.current_version += 1
        review.updated_at = datetime.now(UTC)
        review.current_draft_version_id = new_draft.id
        review.current_validation_snapshot_id = snapshot.id
        review.acknowledged_warnings_json = "[]"
        review.status = "open"
        intake.review_version = review.current_version
        await self.repository.save_review_bundle(
            session,
            review=review,
            draft=new_draft,
            snapshot=snapshot,
            issues=issues,
            edits=review_edits,
        )
        return await self.get_review(session, tenant_id=tenant_id, intake_run_id=intake_run_id)

    async def acknowledge_warning(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        intake_run_id: str,
        expected_review_version: int,
        warning_code: str,
    ) -> dict[str, Any]:
        review, _, _ = await self._current_records(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        self._check_version(review, expected_review_version)
        snapshot = await self.repository.get_snapshot(
            session, tenant_id=tenant_id, snapshot_id=review.current_validation_snapshot_id
        )
        issues = await self.repository.list_issues(
            session, tenant_id=tenant_id, snapshot_id=review.current_validation_snapshot_id
        )
        if snapshot is None or not any(
            item.code == warning_code and item.severity == "warning" for item in issues
        ):
            raise ReviewError(
                "WARNING_NOT_FOUND",
                "warning is not present in the current validation",
            )
        acknowledged = set(json.loads(review.acknowledged_warnings_json))
        acknowledged.add(warning_code)
        review.acknowledged_warnings_json = json.dumps(sorted(acknowledged))
        review.current_version += 1
        review.updated_at = datetime.now(UTC)
        await session.commit()
        return await self.get_review(session, tenant_id=tenant_id, intake_run_id=intake_run_id)

    async def revalidate(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        intake_run_id: str,
        actor_user_id: str,
        expected_review_version: int,
    ) -> dict[str, Any]:
        review, draft, intake = await self._current_records(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        self._check_version(review, expected_review_version)
        payload = DraftFulfillmentRequest.model_validate(json.loads(draft.payload_json))
        fields = [ReviewField.model_validate(item) for item in json.loads(draft.fields_json)]
        report = _review_report(
            payload,
            tenant_id=tenant_id,
            fixture="valid",
            received_at=intake.started_at,
            fields=fields,
        )
        next_version = await self.repository.next_draft_version(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        new_draft, snapshot, issues = _version_bundle(
            tenant_id=tenant_id,
            intake_run_id=intake_run_id,
            payload=payload,
            fields=fields,
            report=report,
            version=next_version,
            source="revalidation",
            actor_user_id=actor_user_id,
            prior_version_id=draft.id,
        )
        review.current_version += 1
        review.updated_at = datetime.now(UTC)
        review.current_draft_version_id = new_draft.id
        review.current_validation_snapshot_id = snapshot.id
        review.acknowledged_warnings_json = "[]"
        review.status = "open"
        intake.review_version = review.current_version
        await self.repository.save_review_bundle(
            session,
            review=review,
            draft=new_draft,
            snapshot=snapshot,
            issues=issues,
        )
        return await self.get_review(session, tenant_id=tenant_id, intake_run_id=intake_run_id)

    async def _current_records(
        self, session: AsyncSession, *, tenant_id: str, intake_run_id: str
    ) -> tuple[Review, DraftVersion, IntakeRun]:
        review = await self.repository.get(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        intake = await self.intake_repository.get(
            session, tenant_id=tenant_id, intake_run_id=intake_run_id
        )
        if review is None or intake is None:
            raise ReviewError("REVIEW_NOT_FOUND", "review not found")
        draft = await self.repository.get_draft(
            session, tenant_id=tenant_id, draft_version_id=review.current_draft_version_id
        )
        if draft is None:
            raise ReviewError("REVIEW_STATE_INCOMPLETE", "current draft is missing")
        return review, draft, intake

    @staticmethod
    def _check_version(review: Review, expected: int) -> None:
        if review.current_version != expected:
            raise ReviewError(
                "STALE_REVIEW_VERSION",
                "the draft changed after this review was loaded; refresh before continuing",
                current_version=review.current_version,
            )


def _demo_fixture(
    *, tenant_id: str, intake_run_id: str, fixture: ReviewFixture, artifact_id: str
) -> tuple[DraftFulfillmentRequest, list[ReviewField]]:
    suffix = tenant_id.removeprefix("tenant-").upper()
    reference = f"REQ-{suffix}-100"
    source_text = (
        "Harborline synthetic request. "
        f"Customer ACCT-{suffix}; reference {reference}; origin ORIGIN-{suffix}; "
        "ship date 2026-09-12; destination US 02110; service STANDARD; "
        "SKU-100 quantity 2 EA."
    )
    content_hash = hashlib.sha256(source_text.encode()).hexdigest()

    def evidence(ref_id: str, excerpt: str, start: int) -> ReviewEvidence:
        return ReviewEvidence(
            ref_id=ref_id,
            artifact_id=artifact_id,
            excerpt=excerpt,
            content_sha256=content_hash,
            char_start=start,
            char_end=start + len(excerpt),
        )

    values = {
        "customer_account_code": f"ACCT-{suffix}",
        "external_request_reference": reference,
        "requested_ship_date": date(2026, 9, 12),
        "origin_code": f"ORIGIN-{suffix}",
        "destination.country_code": "US",
        "destination.postal_code": "02110",
        "service_level": "STANDARD",
        "line_items[0].sku": "SKU-100",
        "line_items[0].quantity": 2,
        "line_items[0].unit": "EA",
    }
    payload = DraftFulfillmentRequest(
        tenant_id=tenant_id,
        customer_account_code=values["customer_account_code"],
        external_request_reference=values["external_request_reference"],
        requested_ship_date=values["requested_ship_date"],
        origin_code=values["origin_code"],
        destination={"country_code": "US", "postal_code": "02110"},
        service_level="STANDARD",
        line_items=[{"sku": "SKU-100", "quantity": 2, "unit": "EA"}],
        source_artifact_ids=[artifact_id],
    )
    fields = [
        ReviewField(
            path=path,
            original_value=value,
            normalized_value=value,
            status="extracted",
            evidence=[evidence(f"ev-{intake_run_id}-{index}", str(value), index * 10)],
            extractor="synthetic-extraction-1",
        )
        for index, (path, value) in enumerate(values.items())
    ]
    if fixture == "missing":
        payload = payload.model_copy(
            update={"destination": payload.destination.model_copy(update={"postal_code": None})}
        )
        missing = next(item for item in fields if item.path == "destination.postal_code")
        missing.original_value = None
        missing.normalized_value = None
        missing.status = "missing"
        missing.evidence = [
            evidence(f"ev-{intake_run_id}-postal-hint", "destination postal 02110", 80)
        ]
    elif fixture == "conflict":
        conflict = next(item for item in fields if item.path == "external_request_reference")
        conflict.status = "conflicting"
        conflict.evidence.append(
            evidence(f"ev-{intake_run_id}-conflict", "reference REQ-A-101", 100)
        )
    return payload, fields


def _review_report(
    payload: DraftFulfillmentRequest,
    *,
    tenant_id: str,
    fixture: ReviewFixture,
    received_at: datetime,
    fields: list[ReviewField],
) -> ValidationReport:
    report = validate_request(
        payload,
        master_data=synthetic_master_data(tenant_id),
        received_at=received_at,
    )
    if any(field.status == "conflicting" for field in fields):
        conflict = ValidationIssue(
            code="CONFLICTING_EVIDENCE",
            severity="warning",
            field_paths=[field.path for field in fields if field.status == "conflicting"],
            safe_message="source evidence contains conflicting values; choose the supported value",
            suggested_action="select the evidence that matches the request",
        )
        report = report.model_copy(
            update={
                "issues": [*report.issues, conflict],
                "review_route": "needs_review",
            }
        )
    if fixture == "missing" and not any(issue.severity == "blocking" for issue in report.issues):
        raise ReviewError("FIXTURE_INVALID", "missing fixture did not produce a blocking issue")
    return report


def _version_bundle(
    *,
    tenant_id: str,
    intake_run_id: str,
    payload: DraftFulfillmentRequest,
    fields: list[ReviewField],
    report: ValidationReport,
    version: int,
    source: str,
    actor_user_id: str,
    prior_version_id: str | None,
) -> tuple[DraftVersion, ValidationSnapshot, list[ValidationIssueRecord]]:
    draft_id = f"draft-{uuid4().hex}"
    snapshot_id = f"validation-{uuid4().hex}"
    serialized = payload.model_dump(mode="json")
    draft = DraftVersion(
        id=draft_id,
        tenant_id=tenant_id,
        intake_run_id=intake_run_id,
        version=version,
        payload_json=json.dumps(serialized, sort_keys=True, separators=(",", ":")),
        fields_json=json.dumps(
            [item.model_dump(mode="json") for item in fields],
            sort_keys=True,
            separators=(",", ":"),
        ),
        payload_sha256=payload_sha256(payload),
        source=source,
        actor_user_id=actor_user_id,
        prior_version_id=prior_version_id,
        created_at=datetime.now(UTC),
    )
    snapshot = ValidationSnapshot(
        id=snapshot_id,
        tenant_id=tenant_id,
        intake_run_id=intake_run_id,
        draft_version_id=draft_id,
        policy_version=report.policy_version,
        rules_fingerprint=RULES_FINGERPRINT,
        report_json=report.model_dump_json(),
        created_at=report.validated_at,
    )
    issues = [
        ValidationIssueRecord(
            id=f"issue-{uuid4().hex}",
            tenant_id=tenant_id,
            validation_snapshot_id=snapshot_id,
            code=issue.code,
            severity=issue.severity,
            field_paths_json=json.dumps(issue.field_paths),
            safe_message=issue.safe_message,
            evidence_refs_json=json.dumps(issue.evidence_refs),
            rule_refs_json=json.dumps(issue.rule_refs or ["sop:harborline:fulfillment:1"]),
            created_at=datetime.now(UTC),
        )
        for issue in report.issues
    ]
    return draft, snapshot, issues


def _edited_fields(
    fields: list[ReviewField], *, edits: list[dict[str, Any]], normalized_payload: dict[str, Any]
) -> list[ReviewField]:
    by_path = {field.path: field for field in fields}
    for edit in edits:
        path = edit["path"]
        field = by_path[path]
        value = _get_path(normalized_payload, path)
        selected = set(edit["evidence_ref_ids"])
        field.original_value = field.normalized_value
        field.normalized_value = value
        field.status = "operator_corrected"
        field.evidence = [item for item in field.evidence if item.ref_id in selected]
        field.extractor = "operator"
    return list(by_path.values())


def _issue_view(issue: ValidationIssueRecord) -> dict[str, Any]:
    return {
        "id": issue.id,
        "code": issue.code,
        "severity": issue.severity,
        "field_paths": json.loads(issue.field_paths_json),
        "safe_message": issue.safe_message,
        "evidence_refs": json.loads(issue.evidence_refs_json),
        "rule_refs": json.loads(issue.rule_refs_json),
        "acknowledged": issue.acknowledged,
        "resolved": issue.resolved,
    }


def _get_path(payload: dict[str, Any], path: str) -> Any:
    if path.startswith("line_items["):
        index_text, field_name = path.removeprefix("line_items[").split("].", 1)
        return payload["line_items"][int(index_text)][field_name]
    current: Any = payload
    for part in path.split("."):
        current = current[part]
    return current


def _set_path(payload: dict[str, Any], path: str, value: Any) -> None:
    if path.startswith("line_items["):
        index_text, field_name = path.removeprefix("line_items[").split("].", 1)
        payload["line_items"][int(index_text)][field_name] = value
        return
    parts = path.split(".")
    current = payload
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value
