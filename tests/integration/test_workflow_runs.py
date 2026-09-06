import pytest

from packages.db.models import IntakeRun, Tenant
from packages.db.repositories import IntakeRunRepository


@pytest.mark.asyncio
async def test_workflow_runs_are_tenant_scoped(db_session_factory) -> None:
    async with db_session_factory() as session:
        session.add_all(
            [
                Tenant(id="tenant-a", name="Tenant A", status="active"),
                Tenant(id="tenant-b", name="Tenant B", status="active"),
                IntakeRun(
                    id="run-a",
                    tenant_id="tenant-a",
                    source_channel="demo",
                    status="review_required",
                    graph_thread_id="run-a",
                ),
            ]
        )
        await session.commit()

        repository = IntakeRunRepository()
        assert await repository.get(session, tenant_id="tenant-a", intake_run_id="run-a")
        assert await repository.get(session, tenant_id="tenant-b", intake_run_id="run-a") is None
        assert {
            run.tenant_id for run in await repository.list_for_tenant(session, tenant_id="tenant-b")
        } == set()
