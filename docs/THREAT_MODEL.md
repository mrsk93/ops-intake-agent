# Ops Intake Agent Threat Model

Status: maintained through M11; this is an engineering threat model, not a
formal certification.

## Assets

Tenant membership and authorization, authentication tokens, source artifacts,
OCR/model/provider outputs, canonical drafts, SOP rules, audit metadata,
idempotency state and operational action authorization.

## Actors and entry points

- Unauthenticated internet client: login and health endpoints.
- Authenticated tenant user: intake, artifact, review, preview and execution
  routes, constrained by current database membership and role.
- Untrusted document author: can place arbitrary text, links, formulas and
  instruction-like content in a synthetic artifact.
- Model/provider failure or compromise: may return malformed, unsupported or
  adversarial structured output through a provider port.
- Worker/operator: runs bounded retention, recovery and reset commands.
- Infrastructure attacker: can target the API, Redis, PostgreSQL, object
  storage or container supply chain.

Trust boundaries are the bearer-token boundary, tenant membership query,
quarantine/storage boundary, parser/OCR boundary, model-provider port,
deterministic policy boundary, review/approval boundary and operations port.
The model never receives operational credentials or a direct tool definition.

## STRIDE-style abuse cases and controls

| Category | Abuse case | Control | Verification |
| --- | --- | --- | --- |
| Spoofing | forged/expired token or suspended membership | JWT expiry/signature plus database user, tenant and membership status check on every request | `tests/integration/test_identity.py` |
| Tampering | edit an old draft or preview | immutable versions, evidence-bound edits, optimistic review version and payload hash | `tests/integration/test_review_api.py` |
| Repudiation | deny an approval or execution | approval, attempts, safe receipt and audit timeline records | `tests/integration/test_operations_api.py` |
| Information disclosure | cross-tenant intake, SOP, artifact or audit lookup | tenant predicate inside repository/storage/retrieval queries and generic not-found responses | `tests/integration/test_identity.py`, `tests/integration/test_retrieval.py` |
| Denial of service | login or approval burst | bounded rate-limit port; production requires Redis | `tests/security/test_hardening.py` |
| Elevation of privilege | viewer approves or stale actor executes | role dependency plus current version/authorization/precondition checks | `tests/integration/test_operations_api.py` |
| Supply chain | floating container or unresolved dependency | committed `uv.lock`/`pnpm-lock.yaml` and repository security scan | `scripts/security_scan.py`, CI |
| Prompt/content injection | document asks the model or UI to approve/call tools | content scanner, strict schema/evidence verification, deterministic validation and human approval | `tests/evaluation/test_harness.py`, `tests/unit/test_validation.py` |
| Unsafe export | spreadsheet formula executes in a consumer | formula values are prefixed before display/export | `tests/security/test_hardening.py` |
| Secret exposure | provider error or log includes content/credentials | structured redaction and safe error-code boundary | `tests/security/test_hardening.py` |

## Residual risks

- The demo does not implement a real malware scanner, external KMS, WAF,
  distributed request tracing, PostgreSQL RLS policy or production backup
  executor.
- Redis rate limiting is a provider seam; availability policy and multi-region
  coordination need deployment-specific decisions.
- Container vulnerability scanning and dependency advisories still require
  the organization's approved scanner and networked CI policy.
- The dataset is synthetic and the evaluation thresholds do not establish
  real-world accuracy or compliance.

## Data lifecycle

The demonstration defaults are 30 days for raw/derived artifacts, 7 days for
raw provider output (disabled by default), and 90 days for canonical metadata
and audit records. Expiry removes object-storage content and clears the
storage key while retaining tenant-scoped ID, hash, status, size and safe
rejection/expiry metadata. Synthetic eval fixtures and results remain in the
repository.

Never store or display chain-of-thought. Store evidence references, hashes,
versions, concise decisions, validation issues and bounded external receipts.
