from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
from typing import Literal

from pydantic import Field

from packages.domain.canonical import DomainModel

SOP_SCHEMA_VERSION = "1.0"
RETRIEVAL_ALGORITHM_VERSION = "hybrid-lexical-hash-embedding-1"

SopStatus = Literal["draft", "approved", "retired"]


class SopDocumentRecord(DomainModel):
    id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=240)
    source_name: str = Field(min_length=1, max_length=240)
    version: str = Field(min_length=1, max_length=64)
    status: SopStatus
    effective_from: datetime
    effective_to: datetime | None = None
    approved_by: str | None = Field(default=None, max_length=64)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SopChunkRecord(DomainModel):
    id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(min_length=1, max_length=64)
    document_id: str = Field(min_length=1, max_length=64)
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=4000)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    rule_type: str = Field(min_length=1, max_length=80)
    customer_account_code: str | None = Field(default=None, max_length=64)
    location_code: str | None = Field(default=None, max_length=64)
    service_level: str | None = Field(default=None, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=30)
    embedding: list[float] = Field(min_length=16, max_length=16)


class SopChunkDraft(DomainModel):
    text: str = Field(min_length=1, max_length=4000)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    ordinal: int = Field(ge=0)


class RetrievalQuery(DomainModel):
    tenant_id: str = Field(min_length=1, max_length=64)
    query_text: str = Field(min_length=1, max_length=4000)
    as_of: datetime
    customer_account_code: str | None = Field(default=None, max_length=64)
    location_code: str | None = Field(default=None, max_length=64)
    service_level: str | None = Field(default=None, max_length=64)
    rule_types: list[str] = Field(default_factory=list, max_length=10)
    top_k: int = Field(default=5, ge=1, le=20)


class RuleCitation(DomainModel):
    tenant_id: str
    document_id: str
    chunk_id: str
    title: str
    version: str
    rule_type: str
    excerpt: str = Field(min_length=1, max_length=600)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    effective_from: datetime
    effective_to: datetime | None = None


class RetrievedRule(DomainModel):
    citation: RuleCitation
    rank: int = Field(ge=1)
    score: float = Field(ge=0, le=1)
    lexical_score: float = Field(ge=0, le=1)
    semantic_score: float = Field(ge=-1, le=1)


class RetrievalResult(DomainModel):
    retrieval_run_id: str
    tenant_id: str
    algorithm_version: str
    query_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hits: list[RetrievedRule] = Field(default_factory=list, max_length=20)
    issue_code: Literal["RULE_NOT_FOUND"] | None = None

    @property
    def found_authoritative_rule(self) -> bool:
        return bool(self.hits)


def normalize_tokens(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"[a-z0-9]+", text.casefold())))


def deterministic_embedding(text: str, *, dimensions: int = 16) -> list[float]:
    """Create a stable, local-only vector without sending SOP text to a provider."""

    values = [0.0] * dimensions
    for token in normalize_tokens(text):
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:2], "big") % dimensions
        sign = 1.0 if digest[2] % 2 else -1.0
        values[index] += sign
    norm = math.sqrt(sum(value * value for value in values))
    return [value / norm for value in values] if norm else values


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def chunk_sop_text(text: str, *, max_chars: int = 1200) -> list[SopChunkDraft]:
    if not text.strip():
        raise ValueError("SOP text must not be empty")
    if max_chars < 100:
        raise ValueError("SOP chunk size is too small")

    chunks: list[SopChunkDraft] = []
    cursor = 0
    ordinal = 0
    for paragraph in re.split(r"\n\s*\n", text):
        if not paragraph.strip():
            cursor += len(paragraph) + 2
            continue
        start = text.find(paragraph, cursor)
        if start < 0:
            raise ValueError("SOP chunk boundaries could not be determined")
        for offset in range(0, len(paragraph), max_chars):
            chunk_text = paragraph[offset : offset + max_chars]
            chunk_start = start + offset
            chunks.append(
                SopChunkDraft(
                    text=chunk_text,
                    char_start=chunk_start,
                    char_end=chunk_start + len(chunk_text),
                    ordinal=ordinal,
                )
            )
            ordinal += 1
        cursor = start + len(paragraph)
    return chunks


def retrieval_query_sha256(query: RetrievalQuery) -> str:
    material = "|".join(
        [
            query.tenant_id,
            query.query_text,
            query.as_of.isoformat(),
            query.customer_account_code or "",
            query.location_code or "",
            query.service_level or "",
            ",".join(sorted(query.rule_types)),
            str(query.top_k),
        ]
    )
    return hashlib.sha256(material.encode()).hexdigest()
