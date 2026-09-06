# Implementation Status

Updated: 2026-09-06

## M0 — Repository audit and architecture decisions

Status: Implemented.

- Bootstrapped the empty workspace without overwriting existing files.
- Added platform manifests, Compose configuration, Makefile, CI and ADRs.
- Recorded current official OpenAI/LangGraph documentation URLs, version baselines and access date.
- Added provider ports and deterministic fakes.

## M1 — Local platform and identity/tenancy

Status: Implemented; Compose runtime not locally executable because Docker is unavailable in the environment.

- Added API, worker and Next.js web skeletons.
- Added PostgreSQL/Redis/MinIO Compose services and health/readiness routes.
- Added configuration validation that fails closed for production demo controls/providers.
- Added tenant, user and membership models, migration, seed and safe reset.
- Added bearer authentication and database-backed tenant/role authorization.
- Added cross-tenant and role-isolation tests.

## Checks

- `uv lock --check`: passed; 85 Python packages resolved.
- `CI=true pnpm install --frozen-lockfile`: passed.
- `make lint`: passed; Ruff, web ESLint and TypeScript checks passed.
- `make test-m0`: passed; 7 tests.
- `make test-m1`: passed; 7 tests, with 2 upstream Starlette/httpx deprecation warnings.
- `make test`: passed; 12 tests, with the same 2 warnings.
- `alembic upgrade head` against temporary SQLite: passed; `0001_identity_tenancy` is head.
- Synthetic seed against temporary SQLite: passed.
- `make dev`: not runnable locally because Docker is unavailable/permission denied; Compose remains the CI/hosted-runtime path.
- No OpenAI API key, hosted model, OCR provider or operations system was used.

## Handoff boundary

M0 and M1 are complete. Work stops here before M2 as required. Future LangGraph checkpoint migrations, artifact ingestion, SOP retrieval, extraction, review UI and operational execution remain deferred.
