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


class MockOperations:
    def __init__(
        self,
        *,
        timeout_after_commit_once: bool = False,
        timeout_before_commit_once: bool = False,
        mismatch_readback_once: bool = False,
    ) -> None:
        self.timeout_after_commit_once = timeout_after_commit_once
        self.timeout_before_commit_once = timeout_before_commit_once
        self.mismatch_readback_once = mismatch_readback_once
        self.create_calls = 0
        self.records: dict[tuple[str, str], dict[str, Any]] = {}
        self._after_timeout_used = False
        self._before_timeout_used = False
        self._mismatch_used = False

    async def create_draft(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
        correlation_id: str | None = None,
    ) -> Mapping[str, Any]:
        del correlation_id
        self.create_calls += 1
        key = (tenant_id, idempotency_key)
        if self.timeout_before_commit_once and not self._before_timeout_used:
            self._before_timeout_used = True
            raise TimeoutError("synthetic timeout before remote commit")
        record = self.records.setdefault(
            key,
            {
                "tenant_id": tenant_id,
                "idempotency_key": idempotency_key,
                "remote_id": f"demo-remote-{len(self.records) + 1}",
                "payload": dict(payload),
                "payload_sha256": content_sha256(
                    json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode()
                ),
            },
        )
        if self.timeout_after_commit_once and not self._after_timeout_used:
            self._after_timeout_used = True
            raise TimeoutError("synthetic timeout after remote commit")
        return dict(record)

    async def lookup(self, *, tenant_id: str, idempotency_key: str) -> Mapping[str, Any] | None:
        record = self.records.get((tenant_id, idempotency_key))
        return dict(record) if record else None

    async def read_back(self, *, tenant_id: str, remote_id: str) -> Mapping[str, Any]:
        record = next(
            (
                item
                for (record_tenant, _), item in self.records.items()
                if record_tenant == tenant_id and item["remote_id"] == remote_id
            ),
            None,
        )
        if record is None:
            raise KeyError(remote_id)
        result = dict(record)
        if self.mismatch_readback_once and not self._mismatch_used:
            self._mismatch_used = True
            result["payload_sha256"] = "0" * 64
        return result


class FakeOperations(MockOperations):
    """Backwards-compatible deterministic operations fake."""

    def __init__(self) -> None:
        super().__init__()

    async def create_draft(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
        correlation_id: str | None = None,
    ) -> Mapping[str, Any]:
        result = await super().create_draft(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            payload=payload,
            correlation_id=correlation_id,
        )
        return {
            "tenant_id": tenant_id,
            "idempotency_key": idempotency_key,
            "remote_id": result["remote_id"],
            "payload": result["payload"],
        }
