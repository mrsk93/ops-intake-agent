from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from packages.domain.canonical import DomainModel, EvidenceRef, ExtractedField, ExtractorRef
from packages.domain.parsing import EvidenceCoordinate


class DocumentClass(StrEnum):
    BOOKING_REQUEST = "booking_request"
    BOOKING_AMENDMENT = "booking_amendment"
    LINE_ITEM_ATTACHMENT = "line_item_attachment"
    SUPPORTING_INSTRUCTION = "supporting_instruction"
    UNSUPPORTED_DOCUMENT = "unsupported_document"


class ModelEvidenceRef(DomainModel):
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


class ModelField(DomainModel):
    path: str = Field(min_length=1, max_length=160)
    proposed_value: Any = None
    status: Literal[
        "extracted", "missing", "ambiguous", "conflicting", "invalid", "operator_corrected"
    ]
    quality_score: float | None = Field(default=None, ge=0, le=1)
    quality_basis: list[str] = Field(default_factory=list, max_length=20)
    evidence: list[ModelEvidenceRef] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def enforce_model_boundaries(self) -> ModelField:
        if self.proposed_value is not None and not self.evidence:
            raise ValueError("proposed fields require evidence")
        if self.quality_score is not None and not self.quality_basis:
            raise ValueError("quality_score requires quality_basis")
        return self


class ModelExtractionOutput(DomainModel):
    schema_version: Literal["1.0"]
    fields: list[ModelField] = Field(default_factory=list, max_length=100)


class ModelClassificationOutput(DomainModel):
    label: DocumentClass
    quality_score: float | None = Field(default=None, ge=0, le=1)
    quality_basis: list[str] = Field(default_factory=list, max_length=20)
    evidence: list[ModelEvidenceRef] = Field(default_factory=list, max_length=20)


class ClassificationDecision(DomainModel):
    label: DocumentClass
    quality_score: float | None = Field(default=None, ge=0, le=1)
    quality_basis: list[str] = Field(default_factory=list, max_length=20)
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=20)


class EvidenceInput(DomainModel):
    artifact_id: str = Field(min_length=1, max_length=64)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    coordinate: EvidenceCoordinate
    text: str = Field(max_length=100_000)

    @model_validator(mode="after")
    def coordinate_matches_artifact(self) -> EvidenceInput:
        if self.coordinate.artifact_id != self.artifact_id:
            raise ValueError("evidence coordinate artifact does not match evidence artifact")
        return self


class ExtractionStatus(StrEnum):
    COMPLETED = "completed"
    REFUSED = "refused"
    INVALID = "invalid"
    TRANSIENT_FAILURE = "transient_failure"
    TERMINAL_FAILURE = "terminal_failure"


class ProviderUsage(DomainModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_micros: int | None = Field(default=None, ge=0)


class ExtractionRun(DomainModel):
    run_id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(min_length=1, max_length=64)
    status: ExtractionStatus
    provider: str = Field(min_length=1, max_length=120)
    provider_version: str = Field(min_length=1, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    prompt_version: str = Field(min_length=1, max_length=120)
    schema_version: str = Field(min_length=1, max_length=32)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    request_id: str | None = Field(default=None, max_length=128)
    latency_ms: int | None = Field(default=None, ge=0)
    usage: ProviderUsage = Field(default_factory=ProviderUsage)
    refusal_code: str | None = Field(default=None, max_length=80)
    error_code: str | None = Field(default=None, max_length=80)
    fields: list[ExtractedField] = Field(default_factory=list, max_length=100)


class ExtractionVerificationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_ALLOWED_EXACT_PATHS = {
    "customer_account_code",
    "external_request_reference",
    "requested_ship_date",
    "origin_code",
    "destination.name",
    "destination.address_line_1",
    "destination.address_line_2",
    "destination.city",
    "destination.region",
    "destination.postal_code",
    "destination.country_code",
    "service_level",
    "handling_instructions",
}
_ALLOWED_LINE_PATH = re.compile(
    r"^line_items\[[0-9]{1,3}\]\.(source_line_ref|sku|description|quantity|unit)$"
)


def extraction_output_schema() -> dict[str, Any]:
    return ModelExtractionOutput.model_json_schema()


def classification_output_schema() -> dict[str, Any]:
    return ModelClassificationOutput.model_json_schema()


def evidence_input_hash(evidence: list[EvidenceInput]) -> str:
    material = [item.model_dump(mode="json") for item in evidence]
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def verify_model_extraction(
    raw_output: dict[str, Any],
    *,
    evidence: list[EvidenceInput],
    extractor: ExtractorRef,
    schema_version: str = "1.0",
) -> list[ExtractedField]:
    try:
        parsed = ModelExtractionOutput.model_validate(raw_output)
    except Exception as exc:
        raise ExtractionVerificationError(
            "SCHEMA_INVALID", "model output did not match the extraction schema"
        ) from exc
    if parsed.schema_version != schema_version:
        raise ExtractionVerificationError(
            "SCHEMA_VERSION_MISMATCH", "model schema version is not supported"
        )

    fields: list[ExtractedField] = []
    for model_field in parsed.fields:
        if not _is_allowed_path(model_field.path):
            raise ExtractionVerificationError(
                "UNSUPPORTED_FIELD_PATH", "model proposed a field outside the canonical schema"
            )
        verified_refs = [_verify_evidence(ref, evidence) for ref in model_field.evidence]
        fields.append(
            ExtractedField(
                path=model_field.path,
                proposed_value=model_field.proposed_value,
                normalized_value=None,
                status=model_field.status,
                quality_score=model_field.quality_score,
                quality_basis=model_field.quality_basis,
                evidence=verified_refs,
                extractor=extractor,
            )
        )
    return fields


def verify_model_classification(
    raw_output: dict[str, Any], *, evidence: list[EvidenceInput]
) -> ClassificationDecision:
    try:
        parsed = ModelClassificationOutput.model_validate(raw_output)
    except Exception as exc:
        raise ExtractionVerificationError(
            "CLASSIFICATION_SCHEMA_INVALID", "model classification did not match the schema"
        ) from exc
    if not parsed.evidence:
        raise ExtractionVerificationError(
            "CLASSIFICATION_EVIDENCE_REQUIRED", "classification requires source evidence"
        )
    return ClassificationDecision(
        label=parsed.label,
        quality_score=parsed.quality_score,
        quality_basis=parsed.quality_basis,
        evidence=[_verify_evidence(ref, evidence) for ref in parsed.evidence],
    )


def _is_allowed_path(path: str) -> bool:
    return path in _ALLOWED_EXACT_PATHS or _ALLOWED_LINE_PATH.fullmatch(path) is not None


def _verify_evidence(ref: ModelEvidenceRef, evidence: list[EvidenceInput]) -> EvidenceRef:
    match = next(
        (
            item
            for item in evidence
            if item.artifact_id == ref.artifact_id
            and item.content_sha256 == ref.content_sha256
            and _coordinates_match(ref, item.coordinate)
        ),
        None,
    )
    if match is None:
        raise ExtractionVerificationError(
            "EVIDENCE_NOT_FOUND", "model evidence does not point inside supplied parsed material"
        )
    if ref.excerpt and _normalize(ref.excerpt) not in _normalize(match.text):
        raise ExtractionVerificationError(
            "EVIDENCE_EXCERPT_MISMATCH", "model evidence excerpt does not match parsed material"
        )
    return EvidenceRef.model_validate(ref.model_dump())


def _coordinates_match(ref: ModelEvidenceRef, coordinate: EvidenceCoordinate) -> bool:
    for name in (
        "page",
        "sheet",
        "row_start",
        "row_end",
        "col_start",
        "col_end",
        "char_start",
        "char_end",
    ):
        value = getattr(ref, name)
        if value is not None and value != getattr(coordinate, name):
            return False
    return any(
        getattr(ref, name) is not None for name in ("page", "sheet", "row_start", "char_start")
    )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()
