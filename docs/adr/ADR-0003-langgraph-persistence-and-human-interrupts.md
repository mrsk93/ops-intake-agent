# ADR-0003: LangGraph Persistence and Human Interrupts

- Status: Accepted and implemented for M7
- Date: 2026-09-06

## Decision

Compile the future intake graph with a PostgreSQL-backed checkpointer. Every run uses `thread_id == intake_run_id`, kept below the checkpointer's length limit. Human review uses `interrupt()` with a JSON-serializable review payload and resumes with `Command(resume=...)`.

Large raw documents, OCR text and provider output remain in tenant-scoped storage/database records, not graph checkpoint state. Resumption re-loads and revalidates current durable records. Any side effect must be idempotent or recorded before retry.

## Testing

Unit tests use `InMemorySaver`; restart tests use PostgreSQL. Approval state is not trusted solely because a graph checkpoint exists.

## Current official baseline checked

Accessed 2026-09-06:

- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph package](https://pypi.org/project/langgraph/)

The observed package baseline is `langgraph==1.2.11` with
`langgraph-checkpoint-postgres==3.1.2`. The current API uses
`InMemorySaver` for unit tests, `AsyncPostgresSaver.from_conn_string(...)` for
the PostgreSQL-backed checkpointer, a stable configurable `thread_id`, and
`Command(resume=...)` to continue an `interrupt()` pause. Checkpointer-owned
tables remain separate from the application's Alembic migration chain.
