import json

import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import hash_password
from apps.api.app.main import create_app
from packages.db.models import Membership, Tenant, User
from packages.testkit.fakes import FakeStorage


async def seed_review_identity(factory) -> None:
    async with factory() as session:
        session.add_all(
            [
                Tenant(id="tenant-a", name="Tenant A", status="active"),
                Tenant(id="tenant-b", name="Tenant B", status="active"),
                User(
                    id="reviewer-a",
                    email="reviewer@example.test",
                    display_name="Synthetic Reviewer",
                    password_hash=hash_password("pw"),
                    status="active",
                ),
                User(
                    id="viewer-a",
                    email="viewer@example.test",
                    display_name="Synthetic Viewer",
                    password_hash=hash_password("pw"),
                    status="active",
                ),
            ]
        )
        session.add_all(
            [
                Membership(
                    id="reviewer-membership-a",
                    tenant_id="tenant-a",
                    user_id="reviewer-a",
                    role="reviewer",
                    status="active",
                ),
                Membership(
                    id="viewer-membership-a",
                    tenant_id="tenant-a",
                    user_id="viewer-a",
                    role="viewer",
                    status="active",
                ),
            ]
        )
        await session.commit()


def login(client: TestClient, email: str) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"email": email, "password": "pw"}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-a"}


@pytest.mark.asyncio
async def test_review_edit_is_evidence_bound_and_stale_version_is_rejected(
    db_session_factory, test_settings
) -> None:
    await seed_review_identity(db_session_factory)
    app = create_app(
        test_settings, session_factory=db_session_factory, storage_provider=FakeStorage()
    )
    with TestClient(app) as client:
        headers = login(client, "reviewer@example.test")
        intake = client.post(
            "/api/intakes", headers=headers, json={"source_channel": "demo", "fixture": "valid"}
        )
        assert intake.status_code == 201
        intake_id = intake.json()["id"]
        assert client.post(f"/api/intakes/{intake_id}/submit", headers=headers).status_code == 200

        review_response = client.get(f"/api/intakes/{intake_id}/review", headers=headers)
        assert review_response.status_code == 200
        review = review_response.json()
        quantity_field = next(
            field
            for field in review["draft"]["fields"]
            if field["path"] == "line_items[0].quantity"
        )
        evidence_id = quantity_field["evidence"][0]["ref_id"]

        edited = client.patch(
            f"/api/intakes/{intake_id}/review/fields",
            headers=headers,
            json={
                "expected_review_version": 1,
                "edits": [
                    {
                        "path": "line_items[0].quantity",
                        "value": 3,
                        "evidence_ref_ids": [evidence_id],
                        "reason": "Synthetic correction from source evidence",
                    }
                ],
            },
        )
        assert edited.status_code == 200
        assert edited.json()["review_version"] == 2
        assert edited.json()["draft"]["payload"]["line_items"][0]["quantity"] == 3

        stale = client.patch(
            f"/api/intakes/{intake_id}/review/fields",
            headers=headers,
            json={
                "expected_review_version": 1,
                "edits": [
                    {
                        "path": "line_items[0].quantity",
                        "value": 4,
                        "evidence_ref_ids": [evidence_id],
                        "reason": "Stale synthetic edit",
                    }
                ],
            },
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "STALE_REVIEW_VERSION"


@pytest.mark.asyncio
async def test_missing_and_conflicting_fixtures_are_safe_review_states(
    db_session_factory, test_settings
) -> None:
    await seed_review_identity(db_session_factory)
    app = create_app(
        test_settings, session_factory=db_session_factory, storage_provider=FakeStorage()
    )
    with TestClient(app) as client:
        headers = login(client, "reviewer@example.test")
        missing = client.post(
            "/api/intakes", headers=headers, json={"source_channel": "demo", "fixture": "missing"}
        ).json()
        missing_id = missing["id"]
        client.post(f"/api/intakes/{missing_id}/submit", headers=headers)
        missing_review = client.get(f"/api/intakes/{missing_id}/review", headers=headers).json()
        assert any(issue["severity"] == "blocking" for issue in missing_review["issues"])
        assert (
            client.post(
                f"/api/intakes/{missing_id}/preview",
                headers=headers,
                json={"expected_review_version": 1},
            ).status_code
            == 404
        )

        conflict = client.post(
            "/api/intakes", headers=headers, json={"source_channel": "demo", "fixture": "conflict"}
        ).json()
        conflict_id = conflict["id"]
        client.post(f"/api/intakes/{conflict_id}/submit", headers=headers)
        conflict_review = client.get(f"/api/intakes/{conflict_id}/review", headers=headers).json()
        assert any(issue["code"] == "CONFLICTING_EVIDENCE" for issue in conflict_review["issues"])
        assert "<script>" not in json.dumps(conflict_review)


@pytest.mark.asyncio
async def test_viewer_can_queue_but_cannot_read_review(db_session_factory, test_settings) -> None:
    await seed_review_identity(db_session_factory)
    app = create_app(
        test_settings, session_factory=db_session_factory, storage_provider=FakeStorage()
    )
    with TestClient(app) as client:
        headers = login(client, "viewer@example.test")
        intake = client.post("/api/intakes", headers=headers, json={"source_channel": "demo"})
        assert intake.status_code == 201
        intake_id = intake.json()["id"]
        assert client.post(f"/api/intakes/{intake_id}/submit", headers=headers).status_code == 200
        assert client.get(f"/api/intakes/{intake_id}/review", headers=headers).status_code == 403
