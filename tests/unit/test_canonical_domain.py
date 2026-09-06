from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.domain.canonical import (
    Destination,
    DraftFulfillmentRequest,
    PreviewBuildError,
    ValidationIssue,
    ValidationReport,
    build_action_preview,
    payload_sha256,
)


def test_canonical_request_normalizes_codes_and_reference() -> None:
    request = DraftFulfillmentRequest(
        tenant_id="tenant-a",
        customer_account_code=" acct-a ",
        external_request_reference=" req-001  ",
        origin_code="origin-1",
        service_level="standard",
        destination=Destination(country_code="us", postal_code="02110"),
    )

    assert request.customer_account_code == "ACCT-A"
    assert request.external_request_reference == "REQ-001"
    assert request.destination.country_code == "US"
    assert request.origin_code == "ORIGIN-1"


def test_domain_models_forbid_untrusted_extra_fields_and_invalid_quantity() -> None:
    with pytest.raises(ValidationError):
        DraftFulfillmentRequest(tenant_id="tenant-a", approval=True)
    with pytest.raises(ValidationError):
        DraftFulfillmentRequest(
            tenant_id="tenant-a",
            line_items=[{"sku": "SKU-1", "quantity": 0, "unit": "EA"}],
        )


def test_action_preview_hash_is_immutable_and_deterministic() -> None:
    payload = DraftFulfillmentRequest(
        tenant_id="tenant-a",
        customer_account_code="ACCT-A",
        external_request_reference="REQ-001",
        destination=Destination(country_code="US", postal_code="02110"),
    )
    report = ValidationReport(
        policy_version="policy-1",
        review_route="high_review_confidence",
        validated_at=datetime.now(UTC),
    )
    action = build_action_preview(
        payload=payload,
        report=report,
        intake_run_id="run-1",
        validation_snapshot_id="validation-1",
        now=datetime.now(UTC),
    )

    assert action.payload_sha256 == payload_sha256(payload)
    assert action.idempotency_key
    with pytest.raises(PreviewBuildError):
        build_action_preview(
            payload=payload,
            report=report.model_copy(
                update={
                    "issues": [
                        ValidationIssue(code="BLOCKED", severity="blocking", safe_message="blocked")
                    ],
                    "review_route": "blocked",
                }
            ),
            intake_run_id="run-1",
            validation_snapshot_id="validation-1",
            now=datetime.now(UTC),
        )
