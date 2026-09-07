# Security Checklist

This checklist maps M11 controls to executable checks.

| Control | Evidence |
| --- | --- |
| Authentication and tenant membership rechecked | `apps/api/app/auth/dependencies.py`; `tests/integration/test_identity.py` |
| Role authorization and approval guard | `apps/api/app/intakes/routes.py`; `tests/integration/test_operations_api.py` |
| Login/approval rate limits | `packages/security/rate_limit.py`; `tests/security/test_hardening.py` |
| Content/log/secret redaction | `packages/security/redaction.py`; `tests/security/test_hardening.py` |
| Formula-safe display/export boundary | `packages/security/content_safety.py`; `tests/security/test_hardening.py` |
| Credential encryption seam | `packages/security/credentials.py`; production settings validation |
| Tenant-scoped retention deletion | `packages/artifacts/service.py`; `tests/integration/test_artifacts.py` |
| Synthetic evaluation safety gate | `make eval-fake`; `tests/evaluation/test_harness.py` |
| Secret/container/lockfile hygiene | `make security-scan`; `scripts/security_scan.py` |
| Failure and restore guidance | `docs/OPERATIONS_RUNBOOK.md` |

The checklist is intentionally explicit about what remains deployment-specific:
external KMS, malware scanning, RLS, vulnerability feeds and production backup
execution are not claimed by the synthetic demo.
