# Model Card: Ops Intake Agent

## Summary

Ops Intake Agent is a production-shaped portfolio demonstration of AI-assisted
document intake. The optional model boundary classifies documents and proposes
strictly structured fields with evidence. Deterministic parsing, retrieval,
validation and a human approval gate control any later mock operational write.

## Intended use

- Demonstrate evidence-first extraction from synthetic booking requests.
- Compare deterministic parsing with optional structured model extraction.
- Exercise review, approval, idempotency and read-back recovery seams.
- Provide a reproducible fake-provider evaluation path for engineering review.

## Out of scope

- Autonomous shipment, invoice, customs, payment or label operations.
- Production accuracy, regulatory compliance or calibrated confidence claims.
- Real customer documents, real email accounts, proprietary SOPs or live OMS/WMS
  connections.
- Model-generated SQL, arbitrary model-selected tools or model-controlled
  approval state.

## Data and provenance

The committed dataset and UI fixtures are synthetic and marked
`synthetically generated` / `synthetic-internal`. The mock operations adapter
is deterministic. No OpenAI API key, hosted model, OCR service or operational
system is required by CI or the local fake-provider path.

## System boundary

The provider-neutral `ClassificationProvider` and `ExtractionProvider` ports
accept bounded evidence and return untrusted structured proposals. The
optional OpenAI adapter uses the Responses API structured-output contract with
`store=False`, no tools and explicit refusal/incomplete handling. Provider
metadata, prompt/schema versions, input/output hashes and request IDs are
recorded; raw prompts and chain-of-thought are not stored.

## Evaluation snapshot

The current fake evaluation is version `m10-fake-1`, with 66 synthetic cases.
Field exact match, critical quantity exact match, evidence coverage, missing
field recall, retrieval recall@3, wrong-tenant hits, prompt-injection
auto-approvals, duplicate remote drafts and workflow accuracy meet the current
release gates. See [EVALUATION_REPORT.md](EVALUATION_REPORT.md) and the
machine-readable [result](../evals/results/fake-latest.json).

The reported retrieval precision@3 is `0.336788`; it is retained as a
diagnostic metric and is not hidden. The release gate prioritizes authoritative
recall, no-rule abstention and zero tenant leakage.

## Safety and human oversight

- Uploaded documents, OCR text and model output are untrusted.
- Every proposed non-null field requires evidence and deterministic validation.
- Instruction-like content is flagged and cannot approve or invoke a tool.
- A current reviewer/admin authorization, valid immutable preview and explicit
  approval are required before the mock operations port is called.
- Uncertain execution uses the same idempotency key plus lookup/read-back.

## Limitations and adaptation work

The demonstration does not provide a production malware scanner, external KMS,
PostgreSQL RLS policy, distributed tracing backend, vulnerability feed,
production backup executor or real provider connection. Those are explicit
deployment adaptations documented in the [operations runbook](RUNBOOK.md) and
[threat model](THREAT_MODEL.md).

## Change history

- M5: optional structured-output OpenAI adapter and provider-neutral fake.
- M10: synthetic evaluation dataset and regression harness.
- M11: security, retention, redaction and operations hardening.
- M12: portfolio documentation, demos, visual assets and release rehearsal.
