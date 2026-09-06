from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def memory_checkpointer() -> InMemorySaver:
    return InMemorySaver()


@asynccontextmanager
async def postgres_checkpointer(
    database_url: str, *, setup: bool = False
) -> AsyncIterator[AsyncPostgresSaver]:
    """Open the LangGraph-owned Postgres checkpoint tables separately from Alembic."""

    connection_string = _psycopg_url(database_url)
    async with AsyncPostgresSaver.from_conn_string(connection_string) as checkpointer:
        if setup:
            await checkpointer.setup()
        yield checkpointer


def _psycopg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )
