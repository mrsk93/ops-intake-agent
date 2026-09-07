# ADR-0012: Approval, Idempotency and Recovery

- Status: Accepted
- Date: 2026-09-07

## Decision

Require a reviewer or admin's current database-backed authorization, the
current review/draft/validation versions, an immutable preview hash, passing
deterministic revalidation and explicit approval before invoking the
operations port. Claim the proposed action in the database before the provider
call; a claimed or completed action cannot be approved again.

Use the canonical tenant/payload idempotency key for every provider attempt.
On timeout, look up by that same key first. If no remote record is found,
retry once with the same key. Every candidate receipt is read back and checked
for tenant, idempotency key and canonical payload hash before the action can
become `verified`. Read-back failure remains `uncertain`; a mismatch becomes a
manual exception. Persist only bounded receipt fields, attempt status and
concise audit details, never an untrusted provider payload.

The operations port is provider-neutral. CI uses a deterministic in-memory
fake with before-commit timeout, after-commit timeout and mismatch scenarios;
no operational credentials or external system are required.

## Consequences

- Unauthorized, stale, edited or invalidated previews cannot reach the
  operations provider.
- Retry recovery produces one remote draft for a stable idempotency key.
- Operators have an audit timeline and an explicit manual-exception state
  instead of a false success after an uncertain response.
- A future external adapter must implement lookup and read-back with the same
  tenant and idempotency contract.
