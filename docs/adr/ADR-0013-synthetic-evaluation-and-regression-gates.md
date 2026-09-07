# ADR-0013: Synthetic Evaluation and Regression Gates

- Status: Accepted and implemented for M10
- Date: 2026-09-07

## Decision

Keep the evaluation dataset and fake-provider runner in the repository. The
dataset contains 66 cases across clean digital, tabular, scanned/noisy,
conflict/amendment, missing/ambiguous, adversarial and no-authoritative-rule
categories. Every case is explicitly marked `synthetically generated` and
`synthetic-internal`.

The fake runner grades extraction exactness, critical quantity exactness,
evidence coverage/correctness, missing-field precision/recall, retrieval
recall@3, precision@3, wrong-tenant hits, no-rule abstention, unsafe-content
flags, prompt-injection auto-approval, duplicate remote drafts and workflow
preview/action decisions. It writes metrics and safe case references only;
source text and provider payloads are not copied into reports.

The pull-request gate is `make eval-fake`. Live evaluation is an explicit
opt-in command requiring an API key, model, case cap and positive cost guard;
it is never required for CI.

## Consequences

- Scores are reproducible from a documented local command and a versioned
  dataset.
- Safety regressions fail the gate even when aggregate extraction scores look
  good.
- Hosted evaluation services can be added later without becoming the durable
  record of results.
