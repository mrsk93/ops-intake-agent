import pytest

from packages.domain.canonical import ExtractorRef
from packages.domain.extraction import (
    EvidenceInput,
    ExtractionVerificationError,
    evidence_input_hash,
    verify_model_classification,
    verify_model_extraction,
)
from packages.domain.parsing import EvidenceCoordinate

ARTIFACT_HASH = "a" * 64


def evidence() -> list[EvidenceInput]:
    return [
        EvidenceInput(
            artifact_id="artifact-1",
            content_sha256=ARTIFACT_HASH,
            coordinate=EvidenceCoordinate(artifact_id="artifact-1", page=1),
            text="Request reference REQ-A-100 for account ACCT-A.",
        )
    ]


def extractor() -> ExtractorRef:
    return ExtractorRef(
        extractor_type="model",
        provider="fake-model",
        provider_version="fake-1",
        model="fixture",
        prompt_version="prompt-1",
        schema_version="1.0",
        request_id="req-1",
    )


def test_model_fields_require_verified_evidence_and_retain_provenance() -> None:
    fields = verify_model_extraction(
        {
            "schema_version": "1.0",
            "fields": [
                {
                    "path": "external_request_reference",
                    "proposed_value": "REQ-A-100",
                    "status": "extracted",
                    "quality_score": 0.9,
                    "quality_basis": ["schema_valid", "evidence_present"],
                    "evidence": [
                        {
                            "artifact_id": "artifact-1",
                            "page": 1,
                            "excerpt": "Request reference REQ-A-100",
                            "content_sha256": ARTIFACT_HASH,
                        }
                    ],
                }
            ],
        },
        evidence=evidence(),
        extractor=extractor(),
    )
    assert fields[0].evidence[0].page == 1
    assert fields[0].extractor.provider == "fake-model"


@pytest.mark.parametrize(
    "output,code",
    [
        (
            {
                "schema_version": "1.0",
                "fields": [
                    {
                        "path": "approval",
                        "proposed_value": True,
                        "status": "extracted",
                        "evidence": [],
                    }
                ],
            },
            "SCHEMA_INVALID",
        ),
        (
            {
                "schema_version": "1.0",
                "fields": [
                    {
                        "path": "external_request_reference",
                        "proposed_value": "REQ-A-100",
                        "status": "extracted",
                        "evidence": [
                            {
                                "artifact_id": "artifact-1",
                                "page": 2,
                                "excerpt": "REQ-A-100",
                                "content_sha256": ARTIFACT_HASH,
                            }
                        ],
                    }
                ],
            },
            "EVIDENCE_NOT_FOUND",
        ),
        (
            {
                "schema_version": "1.0",
                "fields": [
                    {
                        "path": "external_request_reference",
                        "proposed_value": "REQ-A-100",
                        "status": "extracted",
                        "evidence": [
                            {
                                "artifact_id": "artifact-1",
                                "page": 1,
                                "excerpt": "untrusted excerpt",
                                "content_sha256": ARTIFACT_HASH,
                            }
                        ],
                    }
                ],
            },
            "EVIDENCE_EXCERPT_MISMATCH",
        ),
    ],
)
def test_unsafe_or_unverifiable_model_outputs_are_rejected(output, code) -> None:
    with pytest.raises(ExtractionVerificationError) as exc_info:
        verify_model_extraction(output, evidence=evidence(), extractor=extractor())
    assert exc_info.value.code == code


def test_evidence_input_hash_is_stable() -> None:
    assert evidence_input_hash(evidence()) == evidence_input_hash(evidence())


def test_classification_also_requires_verified_evidence() -> None:
    decision = verify_model_classification(
        {
            "label": "booking_request",
            "quality_basis": ["fixture_evidence"],
            "evidence": [
                {
                    "artifact_id": "artifact-1",
                    "page": 1,
                    "excerpt": "Reference REQ-A-100",
                    "content_sha256": ARTIFACT_HASH,
                }
            ],
        },
        evidence=evidence(),
    )
    assert decision.label.value == "booking_request"
