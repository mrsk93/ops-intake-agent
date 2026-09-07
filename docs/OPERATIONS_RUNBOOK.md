# Operations Runbook

This runbook covers the fake-provider demo and identifies production
adaptation seams. It contains no customer data or credentials.

## Failure classes

| Failure | Detect | Safe action | Escalation |
| --- | --- | --- | --- |
| Artifact rejected/quarantined | safe artifact code and status | do not parse; request a supported synthetic file | artifact owner |
| Parser/OCR transient failure | stage error code and attempt count | bounded retry, then review | ingestion operator |
| Model timeout/429/invalid schema/refusal | extraction status and provider code | bounded provider retry; preserve evidence; route to review | model/provider owner |
| No authoritative SOP rule | `RULE_NOT_FOUND` | abstain; do not invent a rule or preview | policy owner |
| Missing/conflicting field | validation/review issue | request evidence-backed correction or acknowledgement | reviewer |
| Stale review/preview/approval | 409 conflict code | refresh and revalidate; never replay the old payload | reviewer |
| Unauthorized request | 401/403/404 and audit boundary | do not reveal resource existence; investigate actor | security owner |
| Operations timeout | `uncertain` attempt | lookup by stable idempotency key, read back, then same-key retry only when absent | operations owner |
| Receipt mismatch | `manual_exception` | stop; compare safe hashes/IDs and investigate the remote system | operations owner |
| Worker restart | queue/checkpoint status | resume from persisted state; check idempotency before effects | platform owner |
| Rate-limit rejection | HTTP 429 | wait for the window; investigate abuse if sustained | security owner |
| Database/Redis/object storage readiness failure | `/health/ready` | stop writes and restore dependency health | platform owner |

Standard logs must contain IDs, hashes, versions, safe error codes, outcomes,
counts and timings only. Use `safe_log_event`; never add raw document,
prompt, OCR, model or provider-response fields to a log message.

## Retention and deletion

The demo defaults are 30 days for raw/derived artifacts, 7 days for raw
provider output (disabled unless explicitly enabled), and 90 days for
canonical metadata/audit. `expire_artifacts_for_tenant` deletes object content,
clears the storage key and retains safe artifact metadata for audit. Any real
deployment must document legal holds, tenant-specific policy, deletion proofs
and backup expiry before changing these values.

## Backup/restore adaptation notes

For production, use encrypted PostgreSQL backups or PITR with a documented
retention schedule. Back up object storage with versioning/immutability and
tenant-aware restore manifests. Redis is a queue/rate-limit/checkpoint
dependency, not the source of truth for approvals or receipts; restore it
only according to the selected queue/checkpoint policy. Restore PostgreSQL,
then object metadata/content, then Redis/worker consumers; run migrations,
health checks, tenant-isolation checks and idempotency reconciliation before
resuming writes. Never restore a production backup into the demo bucket or
database names accepted by `scripts/reset_demo.py`.

## Safe commands

```text
make lint
make test
make eval-fake
make security-scan
make db-migrate
make seed
make reset-demo  # development-only; exact target validation and confirmation required
```
