from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.domain.review import ReviewFixture


class IntakeCreate(BaseModel):
    source_channel: Literal["upload", "email", "webhook", "demo"] = "demo"
    external_request_reference: str | None = Field(default=None, max_length=200)
    fixture: ReviewFixture = "valid"


class IntakeView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    source_channel: str
    demo_fixture: str
    status: str
    graph_thread_id: str
    external_request_reference: str | None
    review_version: int
    error_code: str | None
    started_at: datetime
    completed_at: datetime | None


class FieldEdit(BaseModel):
    path: str = Field(min_length=1, max_length=160)
    value: Any = None
    evidence_ref_ids: list[str] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=1, max_length=500)


class EditFieldsRequest(BaseModel):
    expected_review_version: int = Field(ge=1)
    edits: list[FieldEdit] = Field(min_length=1, max_length=50)


class WarningAcknowledgementRequest(BaseModel):
    expected_review_version: int = Field(ge=1)
    warning_code: str = Field(min_length=1, max_length=80)


class RevalidateRequest(BaseModel):
    expected_review_version: int = Field(ge=1)


class PreviewRequest(BaseModel):
    expected_review_version: int = Field(ge=1)


class ApproveRequest(BaseModel):
    expected_review_version: int = Field(ge=1)
    proposed_action_id: str = Field(min_length=1, max_length=64)
    preview_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RecoverRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
