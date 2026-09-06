import pytest

from packages.domain.extraction import EvidenceInput, ExtractionStatus
from packages.domain.parsing import EvidenceCoordinate
from packages.extraction.service import ExtractionService
from packages.testkit.fakes import FakeExtractionProvider

HASH = "a" * 64


def evidence() -> list[EvidenceInput]:
    return [
        EvidenceInput(
            artifact_id="artifact-1",
            content_sha256=HASH,
            coordinate=EvidenceCoordinate(artifact_id="artifact-1", page=1),
            text="Reference REQ-A-100",
        )
    ]


@pytest.mark.asyncio
async def test_fake_provider_path_needs_no_api_key_and_records_versions() -> None:
    provider = FakeExtractionProvider(
        output={
            "schema_version": "1.0",
            "fields": [
                {
                    "path": "external_request_reference",
                    "proposed_value": "REQ-A-100",
                    "status": "extracted",
                    "quality_basis": ["fixture_evidence"],
                    "evidence": [
                        {
                            "artifact_id": "artifact-1",
                            "page": 1,
                            "excerpt": "Reference REQ-A-100",
                            "content_sha256": HASH,
                        }
                    ],
                }
            ],
        }
    )
    run = await ExtractionService(
        provider,
        provider_name="fake-model",
        provider_version="fixture-1",
        model="fixture-model",
    ).run(tenant_id="tenant-a", evidence=evidence(), run_id="run-1")

    assert run.status is ExtractionStatus.COMPLETED
    assert run.fields[0].proposed_value == "REQ-A-100"
    assert run.fields[0].extractor.prompt_version == "prompt-1.0"


@pytest.mark.asyncio
async def test_invalid_output_gets_one_repair_attempt_then_reviewable_failure() -> None:
    provider = FakeExtractionProvider(
        output={
            "schema_version": "1.0",
            "fields": [
                {
                    "path": "approval",
                    "proposed_value": True,
                    "status": "extracted",
                    "evidence": [],
                }
            ],
        }
    )
    run = await ExtractionService(
        provider,
        provider_name="fake-model",
        provider_version="fixture-1",
        max_repair_attempts=1,
    ).run(tenant_id="tenant-a", evidence=evidence())

    assert run.status is ExtractionStatus.INVALID
    assert provider.calls == [None, "SCHEMA_OR_EVIDENCE_VALIDATION"]


@pytest.mark.asyncio
async def test_provider_refusal_is_a_reviewable_extraction_status() -> None:
    run = await ExtractionService(
        FakeExtractionProvider(failure="refusal"),
        provider_name="fake-model",
        provider_version="fixture-1",
    ).run(tenant_id="tenant-a", evidence=evidence())

    assert run.status is ExtractionStatus.REFUSED
    assert run.refusal_code == "PROVIDER_REFUSAL"
