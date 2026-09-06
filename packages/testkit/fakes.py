from collections.abc import Mapping, Sequence
from typing import Any


class FakeClassificationProvider:
    async def classify(
        self, *, tenant_id: str, evidence: Sequence[Mapping[str, Any]]
    ) -> Mapping[str, Any]:
        return {"label": "booking_request", "tenant_id": tenant_id, "evidence_count": len(evidence)}


class FakeExtractionProvider:
    async def extract(
        self,
        *,
        tenant_id: str,
        evidence: Sequence[Mapping[str, Any]],
        schema_version: str,
        prompt_version: str,
    ) -> Mapping[str, Any]:
        return {
            "schema_version": schema_version,
            "tenant_id": tenant_id,
            "prompt_version": prompt_version,
            "fields": [],
        }


class FakeOcrProvider:
    async def recognize(
        self, *, tenant_id: str, artifact_id: str, content: bytes
    ) -> Mapping[str, Any]:
        return {
            "artifact_id": artifact_id,
            "tenant_id": tenant_id,
            "text": "",
            "content_sha256": "",
        }


class FakeStorage:
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], bytes] = {}

    async def put(self, *, tenant_id: str, key: str, content: bytes, content_type: str) -> str:
        del content_type
        self._objects[(tenant_id, key)] = content
        return key

    async def get(self, *, tenant_id: str, key: str) -> bytes:
        return self._objects[(tenant_id, key)]

    async def delete(self, *, tenant_id: str, key: str) -> None:
        self._objects.pop((tenant_id, key), None)


class FakeOperations:
    async def create_draft(
        self, *, tenant_id: str, idempotency_key: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return {
            "tenant_id": tenant_id,
            "idempotency_key": idempotency_key,
            "remote_id": "demo-remote-id",
            "payload": dict(payload),
        }

    async def lookup(self, *, tenant_id: str, idempotency_key: str) -> Mapping[str, Any] | None:
        return None

    async def read_back(self, *, tenant_id: str, remote_id: str) -> Mapping[str, Any]:
        return {"tenant_id": tenant_id, "remote_id": remote_id}
