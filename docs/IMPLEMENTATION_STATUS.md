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

## M2 — Artifact ingestion/storage/safety

Status: Implemented.

- Added bounded streaming ingestion, SHA-256 identity, filename sanitization and byte-signature/MIME checks.
- Added quarantine → accepted/rejected lifecycle behind tenant-scoped local/S3-compatible storage ports.
- Added immutable artifact metadata, tenant-local deduplication, amendment detection, retention deletion and safe download/view/parse routes.
- Rejected encrypted, macro-like, mismatched, unsupported, oversized and empty inputs with safe reason codes.

## M3 — Deterministic parsing and evidence map

Status: Implemented.

- Added deterministic CSV, XLSX, email and digital PDF parsers with configured page/sheet/row/text limits.
- Added image/scanned-PDF OCR routing through the `OcrProvider` port and deterministic OCR fakes.
- Added versioned parsed artifact models with page, sheet, row, column and character coordinates plus exact text hashes and warnings.
- Added exact normalized header mapping; fuzzy or model-based header guesses are not used.

## M4 — Canonical domain, schemas and validation

Status: Implemented.

- Added strict canonical fulfillment, evidence, validation-report and immutable
  action-preview models with deterministic hashes and stable idempotency keys.
- Added tenant-specific synthetic master data and deterministic required-field,
  cross-field, postal, SKU/unit, service-level and untrusted-instruction gates.
- Added quality/review routing without treating quality scores as calibrated
  probabilities; blocking issues cannot produce an action preview.

## M5 — Model providers and extraction

Status: Implemented.

- Added provider-neutral classification/extraction ports, strict model output
  schemas, evidence coordinate/excerpt verification and unsupported-path
  rejection.
- Added a hash-addressed deterministic fake with schema-repair, timeout and
  refusal scenarios; CI remains API-key free.
- Added an optional OpenAI Responses adapter using strict `text.format` JSON
  Schema output, no tools and `store=False`, with explicit refusal/incomplete
  handling and version/request/usage metadata.

## Checks

- `uv lock --check`: passed; 87 Python packages resolved, including `pypdf==6.17.0` and `python-multipart==0.0.32`.
- `CI=true pnpm install --frozen-lockfile`: passed.
- `make lint`: passed; Ruff, web ESLint and TypeScript checks passed.
- `make test-m0`: passed; 16 tests.
- `make test-m1`: passed; 11 tests, with 2 upstream Starlette/httpx deprecation warnings.
- `make test-m2`: passed; artifact safety, lifecycle, deduplication, retention and tenant-isolation tests.
- `make test-m3`: passed; deterministic CSV/XLSX/email/OCR parser and evidence-map tests.
- `make test-m4`: pending final M4/M5 verification.
- `make test-m5`: pending final M4/M5 verification.
- `make test`: passed; 25 tests, with the same 2 upstream Starlette/httpx deprecation warnings.
- `alembic upgrade head` against temporary SQLite: passed; `0002_artifact_ingestion` is head.
- Synthetic seed against temporary SQLite: passed.
- `make dev`: not runnable locally because Docker is unavailable/permission denied; Compose remains the CI/hosted-runtime path.
- No OpenAI API key, hosted model, OCR provider or operations system was used.

## Handoff boundary

M0 through M3 are complete. Canonical schemas/validation, SOP retrieval, extraction, review UI, durable workflow interrupts and operational execution remain deferred.
