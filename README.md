# Ops Intake Agent

Evidence-first AI document intake with human review, tenant isolation,
deterministic validation and guarded idempotent mock operations.

> Ops Intake Agent is a production-shaped portfolio demonstration. It is not
> an autonomous agent, a compliance claim or a connection to a real OMS/WMS.
> All committed documents, rules, evaluation cases and operational responses
> are synthetic.

[![M0–M12 release](https://img.shields.io/badge/release-v0.1.0-1f674e)](https://github.com/mrsk93/ops-intake-agent/releases/tag/v0.1.0)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-15.5.3-000000?logo=next.js&logoColor=white)](https://nextjs.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.11-1C3C3C)](https://pypi.org/project/langgraph/)

## Why this project exists

Operations teams receive booking and fulfillment requests as email text, PDFs,
images and spreadsheets. The data is inconsistent, but the consequences of
guessing a SKU, quantity, service level or address are operationally serious.

This project demonstrates a safer boundary:

> AI interprets bounded untrusted content; deterministic policy, evidence and a
> human control the operational write.

The canonical workflow produces a `DraftFulfillmentRequest`, routes uncertainty
to review, creates an immutable action preview and calls only a provider-neutral
mock operations adapter after current authorization and explicit approval.

## Capabilities

| Area | Implemented behavior |
| --- | --- |
| Intake | Browser/API intake metadata and tenant-scoped artifact upload. |
| Formats | Deterministic email, PDF, CSV, XLSX and image/OCR routing with limits. |
| Safety | Quarantine lifecycle, byte/type checks, duplicate control and untrusted-content scanning. |
| Extraction | Strict schema-constrained classification/extraction with per-field evidence. |
| Retrieval | Versioned, effective-date, tenant-filtered SOP retrieval with citations. |
| Validation | Required-field, master-data, date, postal, unit, service and instruction gates. |
| Workflow | LangGraph state with stable `thread_id`, PostgreSQL persistence seam and human interrupt. |
| Review | Evidence-first three-panel workspace, immutable draft versions and optimistic review locks. |
| Approval | Reviewer/admin authorization, immutable preview hash and immediate revalidation. |
| Execution | Stable idempotency, mock operations adapter, lookup/read-back and receipt verification. |
| Recovery | Uncertain execution, manual exception and tenant-scoped audit timeline. |
| Evaluation | 66 synthetic cases, deterministic graders and CI-safe regression thresholds. |
| Operations | Redaction, rate limits, retention defaults, security scan and recovery runbook. |

## Architecture

```text
Untrusted document/email
        │
        ▼
Quarantine → deterministic parse/OCR → evidence map
                                      │
                                      ▼
                         structured extraction proposal
                                      │
                    evidence verification + tenant rules
                                      │
                                      ▼
                    deterministic validation + review issue
                                      │
                              human review interrupt
                                      │
                         immutable action preview/hash
                                      │
                      current auth + policy revalidation
                                      │
                         idempotent mock operations port
                                      │
                         lookup/read-back + safe audit
```

See [DATA_FLOW.md](docs/DATA_FLOW.md) for trust boundaries and the detailed
flow diagram.

### Trust boundaries

- Uploaded documents, OCR text and model output are untrusted data.
- The model may classify and propose structured fields only.
- Model calls receive no operational credentials and no operational tool
  definitions.
- Every accepted non-null field requires verified source evidence and
  deterministic validation.
- Approval state is database-owned; model output cannot approve or execute.
- No operational write occurs without current membership/role authorization, a
  valid immutable preview and explicit approval.
- An uncertain remote result is resolved with the same idempotency key and
  lookup/read-back; the key is never changed to make a retry succeed.
- Logs and checkpoints retain references, hashes, versions and concise
  decisions—not raw documents, prompts or chain-of-thought.

## Technology

- **API:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- **Workflow:** LangGraph 1.2.11 with `thread_id == intake_run_id`
- **Persistence:** PostgreSQL 16 with pgvector-shaped retrieval seam
- **Queue/cache:** Dramatiq and Redis
- **Object storage:** local filesystem in tests/development; S3-compatible
  MinIO in Compose through a storage port
- **Web:** Next.js 15.5.3, React 19 and TypeScript
- **Providers:** deterministic model, OCR, storage and operations fakes; optional
  OpenAI Responses adapter
- **Quality:** pytest, Ruff, ESLint, TypeScript, committed synthetic evaluation

## Quickstart

### Requirements

- Python 3.12.9
- [uv](https://docs.astral.sh/uv/) 0.12.2
- Node.js 22.21.1
- pnpm 10.33.0
- Docker with Compose for the full local stack

The fake-provider path and test suite do not require an OpenAI API key or any
hosted OCR/operations service.

### Install and start the demo

```bash
git clone https://github.com/mrsk93/ops-intake-agent.git
cd ops-intake-agent

cp .env.example .env
uv sync --dev
pnpm install --frozen-lockfile

make db-migrate
make seed
make dev
```

Services:

| Service | URL / command |
| --- | --- |
| API | <http://localhost:8000> |
| API liveness | <http://localhost:8000/health/live> |
| API readiness | <http://localhost:8000/health/ready> |
| Web review shell | <http://localhost:3000> |
| Compose logs | `docker compose logs -f api worker web` |

Docker is required for PostgreSQL, Redis, MinIO and the full API/worker stack.
If Docker is unavailable, use the standalone web shell and fake-only release
checks described below; no production-like service is silently substituted.

### Synthetic demo identity

`make seed` creates Tenant A and Tenant B plus synthetic users. The local-only
demo password is defined in `scripts/seed_demo.py`; do not reuse it outside a
local development database. Every request resolves membership and role from
the database, and tenant-facing repositories require an explicit tenant
context.

Demo controls and fake providers fail closed under production configuration.

## Fake-only release rehearsal

This is the recommended no-credential verification path:

```bash
cp .env.example .env
uv sync --dev
pnpm install --frozen-lockfile
make release-check
```

`make release-check` verifies the M12 release tree, Python/web lint and type
checks, all tests, the portfolio contract, fake evaluation, security scan and
both deterministic demo stories.

Run the stories individually:

```bash
make demo-injection
make demo-timeout-recovery
make eval-fake
```

Expected safety signals:

- Prompt-injection fixture: `preview_allowed=false`,
  `operational_write_count=0`.
- Timeout-after-commit fixture: `create_calls=1`,
  `remote_record_count=1`, `read_back_verified=true`.

## Configuration

Configuration is loaded from environment variables and validated at startup.
The committed [.env.example](.env.example) is the local fake-provider baseline.

| Setting | Development default | Production posture |
| --- | --- | --- |
| `MODEL_PROVIDER` | `fake` | Explicit configured provider; never receives ops credentials. |
| `OCR_PROVIDER` | `fake` | Explicit OCR implementation and bounded timeout. |
| `OPS_PROVIDER` | `mock` | External adapter only after security/contract review. |
| `ARTIFACT_STORAGE_PROVIDER` | `local` | S3-compatible provider with server-side authorization. |
| `RATE_LIMIT_PROVIDER` | `memory` | Redis is required. |
| `CREDENTIAL_ENCRYPTION_PROVIDER` | `unconfigured` | External KMS/encryption provider is required. |
| `ENABLE_DEMO_CONTROLS` | `true` | Must be disabled. |
| Retention | 30/30/7/90 days | Replace with the approved data policy. |

Production configuration rejects fake/demo controls, in-memory rate limiting,
and the deterministic test credential cipher. See [MODEL_CARD.md](docs/MODEL_CARD.md)
and [OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md) for residual deployment
adaptations.

## API surface

The FastAPI application exposes OpenAPI documentation at `/docs` when running.
The principal routes are:

| Surface | Routes |
| --- | --- |
| Health | `GET /health/live`, `GET /health/ready` |
| Auth | `POST /api/auth/login`, `GET /api/auth/me` |
| Artifacts | `/api/artifacts` upload, list, safe view/download and deterministic parse |
| Intake | `POST/GET /api/intakes`, submit, status and tenant-scoped artifacts |
| Review | review state, evidence-bound edits, warning acknowledgement and revalidation |
| Preview | `POST /api/intakes/{id}/preview` creates an immutable proposed action |
| Approval | `POST /api/intakes/{id}/approve` requires reviewer/admin authorization |
| Recovery | execution status, recovery and audit timeline |

Error responses use safe codes and correlation metadata. Raw prompts, provider
exceptions, credentials, chain-of-thought and cross-tenant identifiers are not
returned.

## Development commands

| Command | Purpose |
| --- | --- |
| `make lint` | Ruff, web ESLint and TypeScript checks |
| `make test` | Full Python test suite |
| `make test-m0` … `make test-m12` | Milestone-specific checks |
| `make db-migrate` | Apply Alembic application migrations |
| `make seed` | Seed synthetic tenants/users |
| `make reset-demo` | Guarded development-only reset |
| `make generate-fixtures` | Regenerate committed synthetic evaluation cases |
| `make eval-fake` | Run the deterministic evaluation and write reports |
| `make eval-live` | Explicitly guarded live-provider seam; never required in CI |
| `make security-scan` | Secret, lockfile and floating-container scan |
| `make dev` | Start the Compose development stack |

Reset is deliberately narrow: it requires `--confirm-reset`, development
environment, an approved database name and the exact demo storage bucket.

## Testing and release evidence

The current M0–M12 release has a 75-test Python suite plus web lint, typecheck
and production build checks. The full fake evaluation contains 66 synthetic
cases and reports extraction, evidence, retrieval, safety and workflow metrics.

- [Evaluation report](docs/EVALUATION_REPORT.md)
- [Committed JSON result](evals/results/fake-latest.json)
- [Threat model](docs/THREAT_MODEL.md)
- [Security checklist](docs/SECURITY_CHECKLIST.md)
- [Operations runbook](docs/OPERATIONS_RUNBOOK.md)
- [Portfolio case study](docs/portfolio/CASE_STUDY.md)
- [120-second demo script](docs/portfolio/DEMO_SCRIPT.md)
- [Synthetic visual and video assets](docs/portfolio/assets/)

The evaluation is reproducible with `make eval-fake`. Scores are synthetic
regression evidence, not calibrated probabilities or a real-world accuracy
claim. The diagnostic retrieval `precision@3` score is reported honestly in
the evaluation report.

## Repository map

```text
apps/api/                 FastAPI routes, auth, config and database wiring
apps/worker/              Worker entry point and queue configuration
apps/web/                 Next.js evidence-first review shell
packages/domain/          Provider/framework-free canonical schemas and policy
packages/artifacts/       Ingestion, quarantine, deduplication and retention
packages/parsing/         Deterministic email/PDF/CSV/XLSX/OCR routing
packages/extraction/      Evidence-bound structured extraction service
packages/retrieval/       Tenant-filtered SOP chunking and retrieval
packages/review/          Draft versions, edits, validation and previews
packages/operations/      Approval, idempotency, execution and recovery
packages/providers/       Provider ports and optional adapters
packages/security/        Redaction, content safety, rate limits and retention
packages/workflow/        Typed LangGraph state, nodes and checkpoints
migrations/               Application Alembic migrations; graph tables separate
evals/                    Synthetic dataset, graders and committed reports
tests/                    Unit, integration, workflow, security and release tests
docs/                     ADRs, threat model, runbooks and portfolio material
```

Domain and policy packages do not import FastAPI, LangGraph, model/OCR SDKs,
ORMs, Redis or storage SDKs. Provider ports and deterministic fakes preserve a
no-paid-service CI path.

## Production adaptation checklist

Before connecting a real source or operational system, add and review:

- approved email/document authorization and tenant mapping;
- malware scanning and production file/rendering isolation;
- external KMS-backed credential encryption and secret rotation;
- Redis-backed distributed rate limits and abuse monitoring;
- PostgreSQL hardening/RLS review in addition to application scoping;
- object-storage versioning, encryption, retention and authorized downloads;
- dependency/container/vulnerability scanning in networked CI;
- backup/PITR restore rehearsal and tenant-isolation verification;
- a real sandbox adapter with contract tests, idempotency and read-back;
- production observability, alerting and incident response ownership.

These are deployment requirements, not claims made by the synthetic demo.

## Architecture decisions and status

The [ADR index](docs/adr/) records platform versions, provider ports, LangGraph
persistence/interrupts, evidence handling, human approval, storage, parsing,
retrieval, review versioning, execution recovery, evaluation and security.

See [IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) for milestone
acceptance checks and known environment limitations. M0–M12 are complete in
the `v0.1.0` release; the plan defines no subsequent milestone.

## License and synthetic-data notice

This repository is a portfolio demonstration. Do not add real client
documents, email addresses, proprietary SOPs, credentials or operational
identifiers. Keep all fixtures and screenshots synthetic.
