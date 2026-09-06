# ADR-0008: Canonical Domain and Deterministic Validation

- Status: Accepted
- Date: 2026-09-06

## Decision

Keep the canonical intake schema, evidence references, validation issues and
action-preview hash in `packages/domain`. Domain code uses Pydantic for typed
external boundaries but does not import FastAPI, an ORM, a queue, a provider
SDK or storage implementation.

Model-proposed values remain optional until deterministic validation succeeds.
Tenant master data is supplied explicitly as a policy context; the synthetic
seed is tenant-specific and never selected from model output. Required fields,
cross-field rules, postal formats, SKU/unit rules and instruction-like content
are evaluated by table-driven policy code.

Action previews hash the normalized canonical payload. A blocking validation
issue prevents preview construction, and the idempotency key includes the
tenant, action version, normalized external reference and payload hash.

## Consequences

- Missing and ambiguous values remain review states rather than guesses.
- The future review/approval workflow can rebuild and revalidate the payload.
- Pydantic model-copy operations must be treated as immutable snapshots by
  callers; untrusted provider dictionaries are always validated first.
