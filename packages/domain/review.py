from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from packages.domain.canonical import DomainModel, EvidenceRef

ReviewFixture = Literal["valid", "missing", "conflict"]


class ReviewEvidence(DomainModel):
    """Safe evidence metadata shown to an operator; source text remains data."""

    ref_id: str = Field(min_length=1, max_length=64)
    artifact_id: str = Field(min_length=1, max_length=64)
    excerpt: str = Field(max_length=1000)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)


class ReviewField(DomainModel):
    path: str = Field(min_length=1, max_length=160)
    original_value: Any = None
    normalized_value: Any = None
    status: Literal[
        "extracted", "missing", "ambiguous", "conflicting", "invalid", "operator_corrected"
    ]
    evidence: list[ReviewEvidence] = Field(default_factory=list, max_length=20)
    extractor: str = Field(min_length=1, max_length=120)


class ReviewRuleCitation(DomainModel):
    rule_ref: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    version: str = Field(min_length=1, max_length=64)
    effective_from: str = Field(min_length=1, max_length=40)
    safe_summary: str = Field(min_length=1, max_length=1000)


class ReviewDraft(DomainModel):
    fields: list[ReviewField] = Field(default_factory=list, max_length=100)
    payload: dict[str, Any]
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReviewView(DomainModel):
    intake_run_id: str
    review_version: int = Field(ge=1)
    status: Literal["open", "submitted", "approved", "stale"]
    draft_version_id: str
    draft: ReviewDraft
    issues: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    rules: list[ReviewRuleCitation] = Field(default_factory=list, max_length=100)
    acknowledged_warnings: list[str] = Field(default_factory=list, max_length=100)
    preview: dict[str, Any] | None = None
    audit: list[dict[str, Any]] = Field(default_factory=list, max_length=200)


def evidence_to_ref(evidence: ReviewEvidence) -> EvidenceRef:
    return EvidenceRef(
        artifact_id=evidence.artifact_id,
        char_start=evidence.char_start,
        char_end=evidence.char_end,
        excerpt=evidence.excerpt,
        content_sha256=evidence.content_sha256,
    )
