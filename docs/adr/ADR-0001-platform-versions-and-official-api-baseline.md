# ADR-0001: Platform Versions and Official API Baseline

- Status: Accepted
- Date: 2026-09-06

## Decision

Use Python 3.12, uv 0.12.2, Node 22, pnpm 10.33.0, FastAPI 0.141-compatible, SQLAlchemy 2.x, and Alembic 1.x. Resolve compatible patch releases into committed lockfiles.

The future model adapter is pinned to `openai==3.8.0` and uses the Responses API. Structured output uses `responses.parse` with a Pydantic schema or the Responses `text.format` JSON Schema configuration. It must explicitly handle refusal/incomplete output and set `store=False` by default for untrusted intake content.

The future workflow baseline is `langgraph==1.2.11` with `langgraph-checkpoint-postgres==3.1.2`. Production graph state uses a durable PostgreSQL checkpointer; tests use `InMemorySaver`.

## Official sources checked

- OpenAI Structured Outputs: https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI Responses create reference: https://developers.openai.com/api/reference/cli/resources/responses/methods/create
- OpenAI Python package: https://pypi.org/project/openai/
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- LangGraph package: https://pypi.org/project/langgraph/
- LangGraph PostgreSQL checkpointer: https://reference.langchain.com/python/langgraph/checkpoint/postgres

All sources were accessed on 2026-09-06.

## Conflicts resolved

The plan's older reference to the generic OpenAI text guide is superseded by the current Structured Outputs guide. Current Responses requests place structured output under `text.format`; older Chat Completions `response_format` examples are not used for the Responses adapter. Current LangGraph documentation uses `InMemorySaver`, `interrupt()` and `Command(resume=...)`; legacy breakpoint URLs are not used as implementation contracts.
