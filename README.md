# Ops Intake Agent

Ops Intake Agent is a production-shaped portfolio demonstration of governed document intake. AI is limited to classification and structured extraction; deterministic policy, evidence and a human control any future operational write.

## M0/M1 local quickstart

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

The API is available at `http://localhost:8000`, the web shell at `http://localhost:3000`, and liveness at `http://localhost:8000/health/live`.

Synthetic demo users use the email addresses in `scripts/seed_demo.py` and the local-only password `Demo-Only-Password-2026!`. Demo controls are rejected by production configuration validation.

## Trust and tenancy rules

Uploaded documents, OCR output and model output are untrusted data. No model provider receives operational credentials or a direct operations tool. Tenant identity is resolved from a signed token plus a tenant membership query, and tenant IDs are required in tenant-facing SQL predicates. M0/M1 has no operational write endpoint.

## Commands

See `Makefile` for lint, unit/security tests, migrations, seed/reset and Compose startup. CI runs fake-only checks and does not require an API key.
