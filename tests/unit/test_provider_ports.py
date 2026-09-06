import pytest

from packages.testkit.fakes import (
    FakeClassificationProvider,
    FakeExtractionProvider,
    FakeOperations,
    FakeStorage,
)


@pytest.mark.asyncio
async def test_fakes_are_deterministic_and_tenant_scoped() -> None:
    classifier = FakeClassificationProvider()
    result = await classifier.classify(tenant_id="tenant-a", evidence=[{"text": "synthetic"}])
    assert result == {"label": "booking_request", "tenant_id": "tenant-a", "evidence_count": 1}

    storage = FakeStorage()
    await storage.put(tenant_id="tenant-a", key="a.txt", content=b"a", content_type="text/plain")
    with pytest.raises(KeyError):
        await storage.get(tenant_id="tenant-b", key="a.txt")

    operations = FakeOperations()
    created = await operations.create_draft(
        tenant_id="tenant-a", idempotency_key="key", payload={"x": 1}
    )
    assert created["tenant_id"] == "tenant-a"

    extraction = FakeExtractionProvider()
    output = await extraction.extract(
        tenant_id="tenant-a", evidence=[], schema_version="1.0", prompt_version="p1"
    )
    assert output["fields"] == []
