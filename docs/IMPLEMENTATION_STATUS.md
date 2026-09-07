# Implementation Status

Updated: 2026-09-07

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

## M6 — SOP ingestion and retrieval

Status: Implemented.

- Added versioned tenant-owned SOP documents and bounded hash-addressed chunks.
- Added approved/effective-date and customer/location/service/rule metadata
  predicates inside the retrieval SQL query.
- Added deterministic lexical plus local hash-embedding ranking, persisted
  retrieval runs/hits and bounded rule citations.
- Added explicit `RULE_NOT_FOUND` abstention and tenant/future/retired rule
  isolation tests.

## M7 — Durable LangGraph workflow

Status: Implemented.

- Added typed checkpoint-safe graph state with stable `thread_id == intake_run_id`.
- Added graph nodes through validation and the human review interrupt, with
  retryable/reviewable/terminal error classification boundaries.
- Added review payload allowlists that retain IDs, hashes, versions and concise
  decisions but reject raw parser/model content from graph state.
- Added PostgreSQL-backed checkpointer context management using the pinned
  LangGraph package APIs; checkpointer-owned tables remain separate from
  application Alembic migrations.
- Added graph reconstruction/resume, stale-review and unsafe-state tests.

## M8 — Review UI and versioning

Status: Implemented.

- Added tenant-scoped intake queue, upload/submit status and review routes.
- Added immutable draft versions, validation snapshots/issues, evidence-bound
  edits, optimistic review versions, warning acknowledgement and
  deterministic revalidation.
- Added immutable action previews bound to the current draft version,
  validation snapshot, review version, payload hash and idempotency key.
- Added the three-panel synthetic review workspace with queue fixtures,
  evidence highlighting, escaped source/model text, issue/rule citations and
  preview invalidation after changes.

## M9 — Approval, guarded execution and recovery

Status: Implemented.

- Added reviewer/admin-only explicit approval with current tenant membership,
  review/draft/validation/hash guards and deterministic revalidation immediately
  before provider execution.
- Added proposed-action claim/status transitions and stable tenant/payload
  idempotency keys; no model output or UI event can invoke the operations port.
- Added deterministic mock operations behavior for before-commit timeout,
  after-commit timeout, lookup/read-back recovery and receipt mismatch.
- Added bounded receipt persistence, execution attempts, manual exceptions and
  tenant-filtered audit/execution timeline routes. No raw provider payload is
  stored.

## Checks

- `uv lock --check`: passed; 87 Python packages resolved, including `pypdf==6.17.0` and `python-multipart==0.0.32`.
- `CI=true pnpm install --frozen-lockfile`: passed.
- `make lint`: passed; Ruff, web ESLint and TypeScript checks passed.
- `make test-m0`: passed; 16 tests.
- `make test-m1`: passed; 11 tests, with 2 upstream Starlette/httpx deprecation warnings.
- `make test-m2`: passed; artifact safety, lifecycle, deduplication, retention and tenant-isolation tests.
- `make test-m3`: passed; deterministic CSV/XLSX/email/OCR parser and evidence-map tests.
- `make test-m4`: passed; 7 canonical-domain and validation tests.
- `make test-m5`: passed; 11 extraction verification, fake-provider and optional-adapter tests.
- `make test-m6`: passed; 5 deterministic SOP chunking and retrieval tests.
- `make test-m7`: passed; 4 graph interrupt/restart and workflow-run isolation tests.
- `make test-m8`: passed; 3 review API versioning, safe-state and authorization tests.
- `make test-m9`: passed; 4 approval, stale/unauthorized guard, timeout recovery and receipt mismatch tests.
- `uv lock --check`: passed after promoting the pinned LangGraph runtime dependencies.
- `make test`: passed; 59 tests, with 1 existing upstream Starlette/anyio deprecation warning.
- `alembic upgrade head` against temporary SQLite: passed through `0007_approval_execution`.
- Synthetic seed against temporary SQLite: passed; reset refusal against an
  unapproved SQLite target was also confirmed.
- Web lint, typecheck and production build passed. The repository remains on
  the plan's Next.js 15.5.3 baseline; the installed runtime-loop skill has a
  Next.js 16.3+ floor, so no runtime-loop probe was claimed.
- `make dev`: not runnable locally because Docker is unavailable/permission denied; Compose remains the CI/hosted-runtime path.
- No OpenAI API key, hosted model, OCR provider or operations system was used.

## Handoff boundary

M0 through M9 are complete. Evaluation, security/operations hardening and
portfolio release remain deferred to M10-M12.
