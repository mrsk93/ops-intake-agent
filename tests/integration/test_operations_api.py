import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import create_app
from packages.testkit.fakes import FakeStorage, MockOperations
from tests.integration.test_review_api import login, seed_review_identity


def create_preview(client: TestClient, headers: dict[str, str]) -> tuple[str, dict]:
    intake = client.post(
        "/api/intakes", headers=headers, json={"source_channel": "demo", "fixture": "valid"}
    ).json()
    intake_id = intake["id"]
    assert client.post(f"/api/intakes/{intake_id}/submit", headers=headers).status_code == 200
    review = client.get(f"/api/intakes/{intake_id}/review", headers=headers).json()
    preview = client.post(
        f"/api/intakes/{intake_id}/preview",
        headers=headers,
        json={"expected_review_version": review["review_version"]},
    )
    assert preview.status_code == 201
    return intake_id, preview.json()


@pytest.mark.asyncio
async def test_stale_approval_is_rejected_without_an_operations_call(
    db_session_factory, test_settings
) -> None:
    await seed_review_identity(db_session_factory)
    operations = MockOperations()
    app = create_app(
        test_settings,
        session_factory=db_session_factory,
        storage_provider=FakeStorage(),
        operations_provider=operations,
    )
    with TestClient(app) as client:
        headers = login(client, "reviewer@example.test")
        intake_id, preview = create_preview(client, headers)
        forbidden = client.post(
            f"/api/intakes/{intake_id}/approve",
            headers=login(client, "viewer@example.test"),
            json={
                "expected_review_version": 1,
                "proposed_action_id": preview["id"],
                "preview_payload_sha256": preview["payload_sha256"],
            },
        )
        assert forbidden.status_code == 403
        assert operations.create_calls == 0
        review = client.get(f"/api/intakes/{intake_id}/review", headers=headers).json()
        quantity = next(
            field
            for field in review["draft"]["fields"]
            if field["path"] == "line_items[0].quantity"
        )
        edited = client.patch(
            f"/api/intakes/{intake_id}/review/fields",
            headers=headers,
            json={
                "expected_review_version": review["review_version"],
                "edits": [
                    {
                        "path": "line_items[0].quantity",
                        "value": 4,
                        "evidence_ref_ids": [quantity["evidence"][0]["ref_id"]],
                        "reason": "Synthetic concurrent correction",
                    }
                ],
            },
        )
        assert edited.status_code == 200
        approval = client.post(
            f"/api/intakes/{intake_id}/approve",
            headers=headers,
            json={
                "expected_review_version": review["review_version"],
                "proposed_action_id": preview["id"],
                "preview_payload_sha256": preview["payload_sha256"],
            },
        )
        assert approval.status_code == 409
        assert approval.json()["detail"]["code"] in {"STALE_REVIEW_VERSION", "STALE_ACTION"}
        assert operations.create_calls == 0


@pytest.mark.asyncio
async def test_timeout_after_remote_commit_is_resolved_by_lookup_and_readback(
    db_session_factory, test_settings
) -> None:
    await seed_review_identity(db_session_factory)
    operations = MockOperations(timeout_after_commit_once=True)
    app = create_app(
        test_settings,
        session_factory=db_session_factory,
        storage_provider=FakeStorage(),
        operations_provider=operations,
    )
    with TestClient(app) as client:
        headers = login(client, "reviewer@example.test")
        intake_id, preview = create_preview(client, headers)
        response = client.post(
            f"/api/intakes/{intake_id}/approve",
            headers=headers,
            json={
                "expected_review_version": 1,
                "proposed_action_id": preview["id"],
                "preview_payload_sha256": preview["payload_sha256"],
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "verified"
        assert response.json()["attempts"] == 1
        assert operations.create_calls == 1
        execution = client.get(f"/api/intakes/{intake_id}/execution", headers=headers)
        assert execution.status_code == 200
        assert execution.json()["receipt"]["verified"] is True


@pytest.mark.asyncio
async def test_uncertain_before_commit_retries_with_same_key_once(
    db_session_factory, test_settings
) -> None:
    await seed_review_identity(db_session_factory)
    operations = MockOperations(timeout_before_commit_once=True)
    app = create_app(
        test_settings,
        session_factory=db_session_factory,
        storage_provider=FakeStorage(),
        operations_provider=operations,
    )
    with TestClient(app) as client:
        headers = login(client, "reviewer@example.test")
        intake_id, preview = create_preview(client, headers)
        response = client.post(
            f"/api/intakes/{intake_id}/approve",
            headers=headers,
            json={
                "expected_review_version": 1,
                "proposed_action_id": preview["id"],
                "preview_payload_sha256": preview["payload_sha256"],
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "verified"
        assert response.json()["attempts"] == 2
        assert operations.create_calls == 2
        assert len(operations.records) == 1


@pytest.mark.asyncio
async def test_mismatched_readback_becomes_manual_exception(
    db_session_factory, test_settings
) -> None:
    await seed_review_identity(db_session_factory)
    operations = MockOperations(mismatch_readback_once=True)
    app = create_app(
        test_settings,
        session_factory=db_session_factory,
        storage_provider=FakeStorage(),
        operations_provider=operations,
    )
    with TestClient(app) as client:
        headers = login(client, "reviewer@example.test")
        intake_id, preview = create_preview(client, headers)
        response = client.post(
            f"/api/intakes/{intake_id}/approve",
            headers=headers,
            json={
                "expected_review_version": 1,
                "proposed_action_id": preview["id"],
                "preview_payload_sha256": preview["payload_sha256"],
            },
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "RECEIPT_MISMATCH"
        execution = client.get(f"/api/intakes/{intake_id}/execution", headers=headers)
        assert execution.json()["status"] == "manual_exception"
