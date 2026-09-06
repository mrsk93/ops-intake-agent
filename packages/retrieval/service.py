from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models import RetrievalHit, RetrievalRun, SopChunk, SopDocument
from packages.db.repositories import SopRepository
from packages.domain.sop import (
    RETRIEVAL_ALGORITHM_VERSION,
    RetrievalQuery,
    RetrievalResult,
    RetrievedRule,
    RuleCitation,
    SopDocumentRecord,
    SopStatus,
    chunk_sop_text,
    cosine_similarity,
    deterministic_embedding,
    normalize_tokens,
    retrieval_query_sha256,
)


class SopIngestionError(ValueError):
    pass


class SopIngestionService:
    async def ingest_text(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        title: str,
        source_name: str,
        version: str,
        status: SopStatus,
        effective_from: datetime,
        effective_to: datetime | None,
        text: str,
        rule_type: str,
        customer_account_code: str | None = None,
        location_code: str | None = None,
        service_level: str | None = None,
        tags: list[str] | None = None,
        approved_by: str | None = None,
        document_id: str | None = None,
    ) -> SopDocumentRecord:
        if status == "approved" and not approved_by:
            raise SopIngestionError("approved SOP documents require an approver")
        if effective_to is not None and effective_to < effective_from:
            raise SopIngestionError("SOP effective end cannot precede its start")
        chunks = chunk_sop_text(text)
        resolved_document_id = document_id or f"sop-{uuid4().hex}"
        content_sha256 = hashlib.sha256(text.encode()).hexdigest()
        document = SopDocument(
            id=resolved_document_id,
            tenant_id=tenant_id,
            title=title,
            source_name=source_name,
            version=version,
            status=status,
            effective_from=effective_from,
            effective_to=effective_to,
            approved_by=approved_by,
            content_sha256=content_sha256,
        )
        session.add(document)
        normalized_tags = sorted({tag.strip().casefold() for tag in (tags or []) if tag.strip()})
        for draft in chunks:
            session.add(
                SopChunk(
                    id=f"{resolved_document_id}-chunk-{draft.ordinal}",
                    tenant_id=tenant_id,
                    sop_document_id=resolved_document_id,
                    ordinal=draft.ordinal,
                    text=draft.text,
                    text_sha256=hashlib.sha256(draft.text.encode()).hexdigest(),
                    char_start=draft.char_start,
                    char_end=draft.char_end,
                    rule_type=rule_type,
                    customer_account_code=_upper(customer_account_code),
                    location_code=_upper(location_code),
                    service_level=_upper(service_level),
                    tags_json=json.dumps(normalized_tags, separators=(",", ":")),
                    embedding_json=json.dumps(
                        deterministic_embedding(draft.text), separators=(",", ":")
                    ),
                )
            )
        await session.commit()
        return SopDocumentRecord(
            id=resolved_document_id,
            tenant_id=tenant_id,
            title=title,
            source_name=source_name,
            version=version,
            status=status,
            effective_from=effective_from,
            effective_to=effective_to,
            approved_by=approved_by,
            content_sha256=content_sha256,
        )


class SopRetrievalService:
    def __init__(self, repository: SopRepository | None = None) -> None:
        self.repository = repository or SopRepository()

    async def retrieve(
        self, session: AsyncSession, *, query: RetrievalQuery, retrieval_run_id: str | None = None
    ) -> RetrievalResult:
        rows = await self.repository.list_effective_chunks(
            session,
            tenant_id=query.tenant_id,
            as_of=query.as_of,
            customer_account_code=_upper(query.customer_account_code),
            location_code=_upper(query.location_code),
            service_level=_upper(query.service_level),
            rule_types=query.rule_types,
        )
        query_hash = retrieval_query_sha256(query)
        query_tokens = set(normalize_tokens(query.query_text))
        query_embedding = deterministic_embedding(query.query_text)
        scored: list[tuple[float, float, float, int, SopChunk, SopDocument]] = []
        for chunk, document in rows:
            chunk_tokens = set(normalize_tokens(chunk.text))
            lexical_score = len(query_tokens & chunk_tokens) / max(len(query_tokens), 1)
            semantic_score = cosine_similarity(
                query_embedding, _load_embedding(chunk.embedding_json)
            )
            semantic_component = max(semantic_score, 0.0)
            metadata_score = _metadata_match_score(query, chunk)
            score = min(
                1.0,
                (0.70 * lexical_score) + (0.25 * semantic_component) + (0.05 * metadata_score),
            )
            if score > 0:
                scored.append(
                    (score, lexical_score, semantic_score, chunk.ordinal, chunk, document)
                )
        scored.sort(key=lambda item: (-item[0], -item[1], item[5].version, item[3], item[4].id))
        selected = scored[: query.top_k]
        result_id = retrieval_run_id or f"retrieval-{uuid4().hex}"
        hits = [
            RetrievedRule(
                citation=RuleCitation(
                    tenant_id=query.tenant_id,
                    document_id=document.id,
                    chunk_id=chunk.id,
                    title=document.title,
                    version=document.version,
                    rule_type=chunk.rule_type,
                    excerpt=chunk.text[:600],
                    content_sha256=chunk.text_sha256,
                    effective_from=document.effective_from,
                    effective_to=document.effective_to,
                ),
                rank=index,
                score=score,
                lexical_score=lexical_score,
                semantic_score=semantic_score,
            )
            for index, (score, lexical_score, semantic_score, _, chunk, document) in enumerate(
                selected, start=1
            )
        ]
        run = RetrievalRun(
            id=result_id,
            tenant_id=query.tenant_id,
            query_sha256=query_hash,
            filter_json=json.dumps(
                {
                    "tenant_id": query.tenant_id,
                    "as_of": query.as_of.isoformat(),
                    "customer_account_code": query.customer_account_code,
                    "location_code": query.location_code,
                    "service_level": query.service_level,
                    "rule_types": sorted(query.rule_types),
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            algorithm_version=RETRIEVAL_ALGORITHM_VERSION,
            top_k=query.top_k,
        )
        db_hits = [
            RetrievalHit(
                id=f"{result_id}-hit-{index}",
                tenant_id=query.tenant_id,
                retrieval_run_id=result_id,
                sop_chunk_id=citation.citation.chunk_id,
                rank=citation.rank,
                score=citation.score,
                lexical_score=citation.lexical_score,
                semantic_score=citation.semantic_score,
            )
            for index, citation in enumerate(hits, start=1)
        ]
        await self.repository.save_retrieval_run(session, run=run, hits=db_hits)
        return RetrievalResult(
            retrieval_run_id=result_id,
            tenant_id=query.tenant_id,
            algorithm_version=RETRIEVAL_ALGORITHM_VERSION,
            query_sha256=query_hash,
            hits=hits,
            issue_code=None if hits else "RULE_NOT_FOUND",
        )


def _metadata_match_score(query: RetrievalQuery, chunk: SopChunk) -> float:
    checks = (
        (query.customer_account_code, chunk.customer_account_code),
        (query.location_code, chunk.location_code),
        (query.service_level, chunk.service_level),
    )
    requested = [pair for pair in checks if pair[0] is not None]
    if not requested:
        return 0.0
    matching = sum(
        1 for requested_value, chunk_value in requested if requested_value == chunk_value
    )
    return matching / len(requested)


def _load_embedding(value: str) -> list[float]:
    try:
        embedding = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise SopIngestionError("stored SOP embedding is invalid") from exc
    if not isinstance(embedding, list) or len(embedding) != 16:
        raise SopIngestionError("stored SOP embedding has an invalid shape")
    return [float(item) for item in embedding]


def _upper(value: str | None) -> str | None:
    return value.upper() if value else value
