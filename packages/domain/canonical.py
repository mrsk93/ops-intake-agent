from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Destination(DomainModel):
    name: str | None = Field(default=None, max_length=200)
    address_line_1: str | None = Field(default=None, max_length=300)
    address_line_2: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=32)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class FulfillmentLine(DomainModel):
    source_line_ref: str | None = Field(default=None, max_length=80)
    sku: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    quantity: int | None = Field(default=None, ge=1)
    unit: str | None = Field(default=None, max_length=32)

    @field_validator("sku", "unit")
    @classmethod
    def normalize_line_codes(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class DraftFulfillmentRequest(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    tenant_id: str = Field(min_length=1, max_length=64)
    customer_account_code: str | None = Field(default=None, max_length=64)
    external_request_reference: str | None = Field(default=None, max_length=200)
    requested_ship_date: date | None = None
    origin_code: str | None = Field(default=None, max_length=64)
    destination: Destination = Field(default_factory=Destination)
    service_level: str | None = Field(default=None, max_length=64)
    line_items: list[FulfillmentLine] = Field(default_factory=list, max_length=500)
    handling_instructions: str | None = Field(default=None, max_length=4000)
    source_artifact_ids: list[str] = Field(default_factory=list, max_length=100)
    amendment_of_intake_id: str | None = Field(default=None, max_length=64)

    @field_validator("customer_account_code", "origin_code", "service_level")
    @classmethod
    def normalize_codes(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("external_request_reference")
    @classmethod
    def normalize_reference(cls, value: str | None) -> str | None:
        return re.sub(r"\s+", " ", value).strip().upper() if value else value


class EvidenceRef(DomainModel):
    artifact_id: str = Field(min_length=1, max_length=64)
    page: int | None = Field(default=None, ge=1)
    sheet: str | None = Field(default=None, max_length=255)
    row_start: int | None = Field(default=None, ge=1)
    row_end: int | None = Field(default=None, ge=1)
    col_start: int | None = Field(default=None, ge=1)
    col_end: int | None = Field(default=None, ge=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    excerpt: str | None = Field(default=None, max_length=1000)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExtractorRef(DomainModel):
    extractor_type: Literal["deterministic", "model", "operator"]
    provider: str = Field(min_length=1, max_length=120)
    provider_version: str = Field(min_length=1, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    prompt_version: str | None = Field(default=None, max_length=120)
    schema_version: str = Field(min_length=1, max_length=32)
    request_id: str | None = Field(default=None, max_length=128)


class ExtractedField(DomainModel):
    path: str = Field(min_length=1, max_length=160)
    proposed_value: Any = None
    normalized_value: Any = None
    status: Literal[
        "extracted", "missing", "ambiguous", "conflicting", "invalid", "operator_corrected"
    ]
    quality_score: float | None = Field(default=None, ge=0, le=1)
    quality_basis: list[str] = Field(default_factory=list, max_length=20)
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=20)
    extractor: ExtractorRef

    @model_validator(mode="after")
    def require_evidence_for_proposed_value(self) -> ExtractedField:
        if self.proposed_value is not None and not self.evidence:
            raise ValueError("proposed fields require at least one evidence reference")
        if self.quality_score is not None and not self.quality_basis:
            raise ValueError("quality_score requires quality_basis")
        return self


class ValidationIssue(DomainModel):
    code: str = Field(min_length=1, max_length=80)
    severity: Literal["blocking", "warning", "info"]
    field_paths: list[str] = Field(default_factory=list, max_length=20)
    safe_message: str = Field(min_length=1, max_length=500)
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)
    rule_refs: list[str] = Field(default_factory=list, max_length=20)
    suggested_action: str | None = Field(default=None, max_length=500)


class ValidationReport(DomainModel):
    policy_version: str = Field(min_length=1, max_length=64)
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=200)
    review_route: Literal["blocked", "needs_review", "high_review_confidence"]
    validated_at: datetime

    @property
    def blocking(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "blocking")

    @property
    def can_preview(self) -> bool:
        return not self.blocking


class ProposedOpsAction(DomainModel):
    action_type: Literal["create_draft_fulfillment_request"]
    action_version: Literal["1"] = "1"
    tenant_id: str = Field(min_length=1, max_length=64)
    intake_run_id: str = Field(min_length=1, max_length=64)
    payload: DraftFulfillmentRequest
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_snapshot_id: str = Field(min_length=1, max_length=64)
    preview_created_at: datetime

    @model_validator(mode="after")
    def verify_hashes(self) -> ProposedOpsAction:
        expected_payload_hash = payload_sha256(self.payload)
        if self.payload_sha256 != expected_payload_hash:
            raise ValueError("payload_sha256 does not match immutable payload")
        if self.payload.tenant_id != self.tenant_id:
            raise ValueError("action and payload tenant IDs must match")
        return self


def payload_sha256(payload: DraftFulfillmentRequest) -> str:
    encoded = json.dumps(
        payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def idempotency_key(*, tenant_id: str, payload: DraftFulfillmentRequest) -> str:
    material = (
        f"{tenant_id}:create_draft_fulfillment_request:1:"
        f"{payload.external_request_reference or ''}:{payload_sha256(payload)}"
    )
    return hashlib.sha256(material.encode()).hexdigest()


class PreviewBuildError(ValueError):
    pass


def build_action_preview(
    *,
    payload: DraftFulfillmentRequest,
    report: ValidationReport,
    intake_run_id: str,
    validation_snapshot_id: str,
    now: datetime,
) -> ProposedOpsAction:
    if report.blocking:
        raise PreviewBuildError("blocking validation issues prevent an action preview")
    if payload.tenant_id == "":
        raise PreviewBuildError("tenant context is required")
    return ProposedOpsAction(
        action_type="create_draft_fulfillment_request",
        tenant_id=payload.tenant_id,
        intake_run_id=intake_run_id,
        payload=payload,
        payload_sha256=payload_sha256(payload),
        idempotency_key=idempotency_key(tenant_id=payload.tenant_id, payload=payload),
        validation_snapshot_id=validation_snapshot_id,
        preview_created_at=now,
    )
