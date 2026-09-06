import hashlib
import json
from collections.abc import AsyncIterable, Mapping, Sequence
from typing import Any

from packages.domain.artifacts import content_sha256
from packages.providers.ports import ModelConfig


class FakeClassificationProvider:
    async def classify(
        self, *, tenant_id: str, evidence: Sequence[Mapping[str, Any]]
    ) -> Mapping[str, Any]:
        return {"label": "booking_request", "tenant_id": tenant_id, "evidence_count": len(evidence)}


class FakeExtractionProvider:
    def __init__(
        self,
        output: Mapping[str, Any] | None = None,
        *,
        fixtures: Mapping[str, Mapping[str, Any]] | None = None,
        failure: str | None = None,
    ) -> None:
        self.output = (
            dict(output) if output is not None else {"schema_version": "1.0", "fields": []}
        )
        self.fixtures = {key: dict(value) for key, value in (fixtures or {}).items()}
        self.failure = failure
        self.calls: list[str | None] = []

    async def extract(
        self,
        *,
        tenant_id: str,
        evidence: Sequence[Mapping[str, Any]],
        schema_version: str,
        prompt_version: str,
        output_schema: Mapping[str, Any] | None = None,
        model_config: ModelConfig | None = None,
        request_id: str | None = None,
        repair_hint: str | None = None,
    ) -> Mapping[str, Any]:
        del tenant_id, output_schema, model_config, prompt_version
        self.calls.append(repair_hint)
        if self.failure == "timeout":
            from packages.providers.model import ModelProviderError

            raise ModelProviderError("PROVIDER_TIMEOUT", "synthetic timeout", retryable=True)
        if self.failure == "refusal":
            from packages.providers.model import ModelProviderRefusal

            raise ModelProviderRefusal()
        fixture_key = hashlib.sha256(
            json.dumps(list(evidence), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        result = dict(self.fixtures.get(fixture_key, self.output))
        result.setdefault("schema_version", schema_version)
        del request_id
        return result


class FakeOcrProvider:
    async def recognize(
        self, *, tenant_id: str, artifact_id: str, content: bytes
    ) -> Mapping[str, Any]:
        return {
            "artifact_id": artifact_id,
            "tenant_id": tenant_id,
            "text": "",
            "content_sha256": content_sha256(content),
            "provider_version": "fake-ocr-1",
        }


class FakeStorage:
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], bytes] = {}

    async def put_stream(
        self,
        *,
        tenant_id: str,
        key: str,
        chunks: AsyncIterable[bytes],
        content_type: str,
    ) -> str:
        content = b"".join([chunk async for chunk in chunks])
        return await self.put(
            tenant_id=tenant_id, key=key, content=content, content_type=content_type
        )

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
