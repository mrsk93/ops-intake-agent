# ADR-0005: Human Approval and Guarded Operations

- Status: Accepted for M9 implementation
- Date: 2026-09-06

## Decision

No operational write may occur without current authorization, a valid immutable preview hash, deterministic validation, explicit approval and a stable idempotency key. The action payload is rebuilt from validated canonical state, never copied from free-form model output.

An uncertain remote response is resolved through lookup by the same idempotency key and read-back verification before any retry. Approval becomes stale after edits, rule changes or validation changes.
