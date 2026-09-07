# Case Study: AI Document Intake With Human Review and Safe System Updates

## 1. The problem

Operations teams receive booking requests as inconsistent emails, PDFs and
spreadsheets. Copying them into an operational system is slow; an autonomous
agent that guesses a SKU, quantity, service level or address can create a
larger incident.

## 2. The design answer

Ops Intake Agent gives interpretation a narrow boundary. Deterministic parsers
handle known tables and digital text first. The optional model returns only a
strict extraction proposal. Each accepted value carries an artifact coordinate,
excerpt and content hash. Tenant-filtered SOP retrieval supplies cited rules;
deterministic validation decides whether a draft is blocked, needs review or
can receive a preview.

## 3. The control point

Review is a durable interrupt, not a chat transcript. Edits create immutable
draft versions and invalidate old previews. Approval reloads the current
tenant membership, draft, validation snapshot, SOP versions and preview hash.
Only then can the provider-neutral mock operations port be called.

## 4. Failure behavior

An instruction-like sentence in a customer document remains document content:
it is flagged, cannot set approval state and cannot call a tool. If a remote
create times out after transmission, the same idempotency key is looked up and
the result is read back before the system reports verified completion. A
mismatch becomes a manual exception.

## 5. Evidence from the repository

- 66 committed synthetic evaluation cases cover clean, tabular, scanned,
  conflicting, missing, adversarial and no-rule scenarios.
- The fake gate reports zero prompt-injection auto-approvals, zero wrong-tenant
  retrieval hits, zero duplicate remote drafts and full evidence coverage.
- 71 automated tests cover the current implementation; the exact command is
  `make test`.
- The UI assets in this release are synthetic visual captures/mockups; no real
  customer material is used.

## 6. Honest production adaptation

A real deployment would require an approved email/document source, a malware
scanner, external key management, production object storage and rate-limit
coordination, PostgreSQL hardening/RLS review, vulnerability scanning and a
real sandbox adapter. Those controls are deliberately ports or residual risks,
not claims of production compliance.

## Before and after

| Capability | Generic AI demo | Ops Intake Agent |
| --- | --- | --- |
| Output | Free-form answer | Strict canonical schema |
| Grounding | Opaque | Field evidence + SOP citations |
| Uncertainty | Fluent guess | Missing / ambiguous / review |
| Tools | Model-triggered | Deterministic gate + approval |
| Retries | May duplicate | Stable key + lookup/read-back |
| Quality | Cherry-picked examples | Committed synthetic eval set |
| Audit | Chat transcript | Versioned run/edit/approval/action trail |

## Portfolio copy

**Title:** AI Document Intake With Human Review and Safe System Updates

**Role:** AI/backend engineer — extraction, LangGraph workflow, RAG, evals and guarded tools

**Description:** Built an AI-assisted intake workflow for booking/order emails,
PDFs and spreadsheets. It extracts schema-validated fields with source
evidence, retrieves customer SOP rules, and pauses for correction/approval
before any write. Approved drafts are created through an idempotent mock
operations adapter and verified by read-back. Includes retry recovery,
prompt-injection controls and a synthetic evaluation suite; it is not a
chatbot or an autonomous writer.
