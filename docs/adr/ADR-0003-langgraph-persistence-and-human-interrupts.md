# ADR-0003: LangGraph Persistence and Human Interrupts

- Status: Accepted for M7 implementation
- Date: 2026-09-06

## Decision

Compile the future intake graph with a PostgreSQL-backed checkpointer. Every run uses `thread_id == intake_run_id`, kept below the checkpointer's length limit. Human review uses `interrupt()` with a JSON-serializable review payload and resumes with `Command(resume=...)`.

Large raw documents, OCR text and provider output remain in tenant-scoped storage/database records, not graph checkpoint state. Resumption re-loads and revalidates current durable records. Any side effect must be idempotent or recorded before retry.

## Testing

Unit tests use `InMemorySaver`; restart tests use PostgreSQL. Approval state is not trusted solely because a graph checkpoint exists.
