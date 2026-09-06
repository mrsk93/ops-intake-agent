from datetime import UTC, datetime, timedelta

import pytest

from packages.db.models import Tenant
from packages.db.repositories import SopRepository
from packages.domain.sop import RetrievalQuery
from packages.retrieval.service import SopIngestionService, SopRetrievalService


async def seed_tenants(factory) -> None:
    async with factory() as session:
        session.add_all(
            [
                Tenant(id="tenant-a", name="Tenant A", status="active"),
                Tenant(id="tenant-b", name="Tenant B", status="active"),
            ]
        )
        await session.commit()


@pytest.mark.asyncio
async def test_retrieval_is_tenant_effective_and_version_scoped(db_session_factory) -> None:
    await seed_tenants(db_session_factory)
    ingestion = SopIngestionService()
    as_of = datetime(2026, 9, 6, 12, tzinfo=UTC)
    async with db_session_factory() as session:
        await ingestion.ingest_text(
            session,
            tenant_id="tenant-a",
            title="Tenant A service rules",
            source_name="tenant-a-sop",
            version="2026.09",
            status="approved",
            effective_from=as_of - timedelta(days=10),
            effective_to=None,
            text="Routine freight may use STANDARD service level. Express requires an exception.",
            rule_type="service_level",
            customer_account_code="ACCT-A",
            service_level="STANDARD",
            approved_by="user-a",
            document_id="sop-a-current",
        )
        await ingestion.ingest_text(
            session,
            tenant_id="tenant-a",
            title="Tenant A future rules",
            source_name="tenant-a-future",
            version="2026.10",
            status="approved",
            effective_from=as_of + timedelta(days=1),
            effective_to=None,
            text="Routine freight may use EXPRESS service level.",
            rule_type="service_level",
            customer_account_code="ACCT-A",
            service_level="EXPRESS",
            approved_by="user-a",
            document_id="sop-a-future",
        )
        await ingestion.ingest_text(
            session,
            tenant_id="tenant-a",
            title="Tenant A retired rules",
            source_name="tenant-a-retired",
            version="2026.01",
            status="retired",
            effective_from=as_of - timedelta(days=100),
            effective_to=as_of - timedelta(days=1),
            text="Routine freight may use EXPRESS service level.",
            rule_type="service_level",
            customer_account_code="ACCT-A",
            service_level="EXPRESS",
            approved_by="user-a",
            document_id="sop-a-retired",
        )
        await ingestion.ingest_text(
            session,
            tenant_id="tenant-b",
            title="Tenant B service rules",
            source_name="tenant-b-sop",
            version="2026.09",
            status="approved",
            effective_from=as_of - timedelta(days=10),
            effective_to=None,
            text="Routine freight may use EXPRESS service level for Tenant B.",
            rule_type="service_level",
            customer_account_code="ACCT-A",
            service_level="EXPRESS",
            approved_by="user-b",
            document_id="sop-b-current",
        )

        result = await SopRetrievalService().retrieve(
            session,
            query=RetrievalQuery(
                tenant_id="tenant-a",
                query_text="Which service level may routine freight use?",
                as_of=as_of,
                customer_account_code="ACCT-A",
                service_level="STANDARD",
                rule_types=["service_level"],
                top_k=5,
            ),
        )

        assert result.issue_code is None
        assert result.hits[0].citation.document_id == "sop-a-current"
        assert {hit.citation.tenant_id for hit in result.hits} == {"tenant-a"}
        assert {hit.citation.document_id for hit in result.hits} == {"sop-a-current"}
        assert await SopRepository().get_retrieval_run(
            session, tenant_id="tenant-a", retrieval_run_id=result.retrieval_run_id
        )
        assert (
            await SopRepository().get_retrieval_run(
                session, tenant_id="tenant-b", retrieval_run_id=result.retrieval_run_id
            )
            is None
        )


@pytest.mark.asyncio
async def test_missing_authoritative_rule_abstains_without_invention(db_session_factory) -> None:
    await seed_tenants(db_session_factory)
    async with db_session_factory() as session:
        await SopIngestionService().ingest_text(
            session,
            tenant_id="tenant-a",
            title="Tenant A standard rule",
            source_name="tenant-a-sop",
            version="1",
            status="approved",
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
            effective_to=None,
            text="Only STANDARD is allowed for ACCT-A.",
            rule_type="service_level",
            customer_account_code="ACCT-A",
            service_level="STANDARD",
            approved_by="user-a",
            document_id="sop-a-only-standard",
        )

        result = await SopRetrievalService().retrieve(
            session,
            query=RetrievalQuery(
                tenant_id="tenant-a",
                query_text="What service level may this request use?",
                as_of=datetime(2026, 9, 6, tzinfo=UTC),
                customer_account_code="UNKNOWN",
                service_level="EXPRESS",
                rule_types=["service_level"],
            ),
        )

        assert result.hits == []
        assert result.issue_code == "RULE_NOT_FOUND"
