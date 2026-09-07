# ADR-0014: Security Hardening and Data Lifecycle

- Status: Accepted and implemented for M11
- Date: 2026-09-07

## Decision

Standard structured events pass through a redaction boundary that retains
tenant/run/provider identifiers, hashes, versions, counts, latency and safe
error codes while replacing content, prompts, documents, payloads, provider
responses and secrets with bounded markers. Provider exception text is never
logged as a standard error field.

Use database-backed membership/role checks on every request and bounded login
and approval/recovery rate limits. Development/test may use the deterministic
in-memory limiter; production configuration requires Redis. Credential storage
uses a provider-neutral encryption port; production configuration requires an
external key-management implementation and rejects the test cipher.

Use 30-day raw/derived artifact retention, 7-day raw provider-output
retention, and 90-day canonical metadata/audit retention as demonstration
defaults. Artifact expiry deletes storage content and retains safe metadata
and hashes for audit. Dependency/container/secret hygiene runs in CI through
lockfile checks and a repository scan; container images may not use `latest`.

## Consequences

- The demo is safe to run without credentials while production defaults fail
  closed around missing operational controls.
- Auditability survives content expiry without retaining source content.
- The external credential and backup/restore adapters remain explicit seams,
  not a claim that the synthetic demo is a production KMS or backup system.
