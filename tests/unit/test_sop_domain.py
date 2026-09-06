from datetime import UTC, datetime

import pytest

from packages.domain.sop import (
    RetrievalQuery,
    chunk_sop_text,
    cosine_similarity,
    deterministic_embedding,
    retrieval_query_sha256,
)


def test_sop_chunking_preserves_source_coordinates_and_hash_embedding_is_stable() -> None:
    text = "Service rules\n\nUse standard service for routine freight.\n\nCutoff is 16:00 UTC."

    chunks = chunk_sop_text(text, max_chars=100)

    assert [chunk.ordinal for chunk in chunks] == [0, 1, 2]
    assert "Use standard service" in chunks[1].text
    assert text[chunks[1].char_start : chunks[1].char_end] == chunks[1].text
    vector = deterministic_embedding(text)
    assert vector == deterministic_embedding(text)
    assert cosine_similarity(vector, vector) == pytest.approx(1.0)


def test_retrieval_query_hash_excludes_no_raw_content_from_storage_contract() -> None:
    query = RetrievalQuery(
        tenant_id="tenant-a",
        query_text="Which service level is allowed for routine freight?",
        as_of=datetime(2026, 9, 6, tzinfo=UTC),
        customer_account_code="ACCT-A",
        service_level="STANDARD",
    )

    assert len(retrieval_query_sha256(query)) == 64
    assert retrieval_query_sha256(query) == retrieval_query_sha256(query)


def test_empty_sop_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        chunk_sop_text("  ")
