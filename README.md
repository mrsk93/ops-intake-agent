# Ops Intake Agent

Ops Intake Agent is a production-shaped portfolio demonstration of governed document intake. AI is limited to classification and structured extraction; deterministic policy, evidence and a human control any future operational write.

## M0–M5 local quickstart

Requirements: Python 3.12, uv 0.12.2, Node 22, pnpm 10.33.0, and Docker Compose for the full stack.

```bash
cp .env.example .env
uv sync --dev
pnpm install --frozen-lockfile
make db-migrate
make seed
make test
make dev
```

The API is available at `http://localhost:8000`, the web shell at `http://localhost:3000`, and liveness at `http://localhost:8000/health/live`. Artifact uploads are accepted at `POST /api/artifacts` with a bearer token and `X-Tenant-ID`; accepted artifacts can be viewed, downloaded or deterministically parsed through their tenant-scoped routes.

Synthetic demo users use the email addresses in `scripts/seed_demo.py` and the local-only password `Demo-Only-Password-2026!`. Demo controls are rejected by production configuration validation.

## Trust and tenancy rules

Uploaded documents, OCR output and model output are untrusted data. No model provider receives operational credentials or a direct operations tool. Tenant identity is resolved from a signed token plus a tenant membership query, and tenant IDs are required in tenant-facing SQL predicates. M0–M5 has no operational write endpoint.

M4 adds the canonical request schema and deterministic policy gate. M5 adds a
hash-addressed fake extraction provider for CI plus an optional OpenAI Responses
adapter. The live adapter is not enabled by default and does not receive
operational tools or credentials.

## Commands

See `Makefile` for lint, unit/security tests, migrations, seed/reset and Compose startup. CI runs fake-only checks and does not require an API key.
