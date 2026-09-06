from collections.abc import AsyncIterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    provider: str
    version: str
    request_id: str | None = None


class ClassificationProvider(Protocol):
    async def classify(
        self, *, tenant_id: str, evidence: Sequence[Mapping[str, Any]]
    ) -> Mapping[str, Any]: ...


class ExtractionProvider(Protocol):
    async def extract(
        self,
        *,
        tenant_id: str,
        evidence: Sequence[Mapping[str, Any]],
        schema_version: str,
        prompt_version: str,
    ) -> Mapping[str, Any]: ...


class OcrProvider(Protocol):
    async def recognize(
        self, *, tenant_id: str, artifact_id: str, content: bytes
    ) -> Mapping[str, Any]: ...


class StoragePort(Protocol):
    async def put_stream(
        self,
        *,
        tenant_id: str,
        key: str,
        chunks: AsyncIterable[bytes],
        content_type: str,
    ) -> str: ...

    async def put(self, *, tenant_id: str, key: str, content: bytes, content_type: str) -> str: ...

    async def get(self, *, tenant_id: str, key: str) -> bytes: ...

    async def delete(self, *, tenant_id: str, key: str) -> None: ...


class OperationsPort(Protocol):
    async def create_draft(
        self, *, tenant_id: str, idempotency_key: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    async def lookup(self, *, tenant_id: str, idempotency_key: str) -> Mapping[str, Any] | None: ...

    async def read_back(self, *, tenant_id: str, remote_id: str) -> Mapping[str, Any]: ...
