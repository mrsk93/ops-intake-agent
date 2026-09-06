from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from packages.domain.canonical import ExtractorRef
from packages.domain.extraction import (
    EvidenceInput,
    ExtractionRun,
    ExtractionStatus,
    ProviderUsage,
    evidence_input_hash,
    verify_model_extraction,
)
from packages.providers.model import ModelProviderError, ModelProviderRefusal
from packages.providers.ports import ExtractionProvider, ModelConfig


class ExtractionService:
    def __init__(
        self,
        provider: ExtractionProvider,
        *,
        provider_name: str,
        provider_version: str,
        model: str | None = None,
        max_repair_attempts: int = 1,
    ) -> None:
        self.provider = provider
        self.provider_name = provider_name
        self.provider_version = provider_version
        self.model = model
        self.max_repair_attempts = max_repair_attempts

    async def run(
        self,
        *,
        tenant_id: str,
        evidence: list[EvidenceInput],
        schema_version: str = "1.0",
        prompt_version: str = "prompt-1.0",
        model_config: ModelConfig | None = None,
        run_id: str | None = None,
    ) -> ExtractionRun:
        resolved_run_id = run_id or f"extraction-{uuid4().hex}"
        input_hash = evidence_input_hash(evidence)
        provider_input = [item.model_dump(mode="json") for item in evidence]
        started = time.monotonic()
        repair_hint: str | None = None
        for attempt in range(self.max_repair_attempts + 1):
            try:
                raw = await self.provider.extract(
                    tenant_id=tenant_id,
                    evidence=provider_input,
                    schema_version=schema_version,
                    prompt_version=prompt_version,
                    model_config=model_config,
                    request_id=resolved_run_id,
                    repair_hint=repair_hint,
                )
                extractor = ExtractorRef(
                    extractor_type="model",
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    model=self.model,
                    prompt_version=prompt_version,
                    schema_version=schema_version,
                    request_id=resolved_run_id,
                )
                fields = verify_model_extraction(
                    dict(raw), evidence=evidence, extractor=extractor, schema_version=schema_version
                )
                return ExtractionRun(
                    run_id=resolved_run_id,
                    tenant_id=tenant_id,
                    status=ExtractionStatus.COMPLETED,
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    model=self.model,
                    prompt_version=prompt_version,
                    schema_version=schema_version,
                    input_sha256=input_hash,
                    output_sha256=_hash_json(raw),
                    request_id=resolved_run_id,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    usage=getattr(self.provider, "last_usage", ProviderUsage()),
                    fields=fields,
                )
            except ModelProviderError as exc:
                if exc.retryable and attempt < self.max_repair_attempts:
                    repair_hint = exc.code
                    continue
                return ExtractionRun(
                    run_id=resolved_run_id,
                    tenant_id=tenant_id,
                    status=(
                        ExtractionStatus.REFUSED
                        if isinstance(exc, ModelProviderRefusal)
                        else (
                            ExtractionStatus.TRANSIENT_FAILURE
                            if exc.retryable
                            else ExtractionStatus.TERMINAL_FAILURE
                        )
                    ),
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    model=self.model,
                    prompt_version=prompt_version,
                    schema_version=schema_version,
                    input_sha256=input_hash,
                    request_id=resolved_run_id,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    usage=getattr(self.provider, "last_usage", ProviderUsage()),
                    refusal_code=exc.code if isinstance(exc, ModelProviderRefusal) else None,
                    error_code=None if isinstance(exc, ModelProviderRefusal) else exc.code,
                )
            except ValueError as exc:
                if attempt < self.max_repair_attempts:
                    repair_hint = "SCHEMA_OR_EVIDENCE_VALIDATION"
                    continue
                return ExtractionRun(
                    run_id=resolved_run_id,
                    tenant_id=tenant_id,
                    status=ExtractionStatus.INVALID,
                    provider=self.provider_name,
                    provider_version=self.provider_version,
                    model=self.model,
                    prompt_version=prompt_version,
                    schema_version=schema_version,
                    input_sha256=input_hash,
                    request_id=resolved_run_id,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    usage=getattr(self.provider, "last_usage", ProviderUsage()),
                    error_code=getattr(exc, "code", "OUTPUT_VALIDATION_FAILED"),
                )
        raise AssertionError("extraction retry loop did not return")


def _hash_json(value: Mapping[str, Any]) -> str:
    import hashlib
    import json

    encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
