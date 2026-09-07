# Ops Intake Agent Evaluation Report

Status: **PASS** for the deterministic fake-provider gate.

- Evaluation version: `m10-fake-1`
- Dataset: [`evals/cases.jsonl`](../evals/cases.jsonl)
- Result JSON: [`evals/results/fake-latest.json`](../evals/results/fake-latest.json)
- Result Markdown: [`evals/results/fake-latest.md`](../evals/results/fake-latest.md)
- Dataset size: 66 cases
- Provenance: synthetic fixtures only

Reproduce this report with:

```bash
make eval-fake
```

## Dataset composition

| Category | Cases |
| --- | ---: |
| Clean digital | 15 |
| CSV/XLSX tabular | 10 |
| Scanned/noisy | 10 |
| Conflict/amendment | 10 |
| Missing/ambiguous | 10 |
| Adversarial mandatory fixtures | 10 |
| No authoritative rule | 1 |

## Metrics

| Area | Metric | Result | Gate |
| --- | --- | ---: | ---: |
| Extraction | Required-field exact match | 1.0 | ≥ 0.99 |
| Extraction | Critical quantity exact match | 1.0 | ≥ 1.0 |
| Extraction | Evidence coverage | 1.0 | ≥ 1.0 |
| Extraction | Evidence correctness | 1.0 | monitored |
| Extraction | Missing-field precision / recall | 1.0 / 1.0 | monitored |
| Retrieval | Recall@3 | 1.0 | ≥ 1.0 |
| Retrieval | Precision@3 | 0.336788 | diagnostic |
| Retrieval | Wrong-tenant hits | 0 | 0 |
| Retrieval | No-rule abstention | 1.0 | ≥ 1.0 |
| Safety | Unsafe-content flag rate | 1.0 | ≥ 1.0 |
| Safety | Prompt-injection auto-approvals | 0 | 0 |
| Safety | Duplicate remote drafts | 0 | 0 |
| Safety | Raw content in result | 0 | 0 |
| Workflow | Preview decision accuracy | 1.0 | ≥ 1.0 |
| Workflow | Remote-action count accuracy | 1.0 | ≥ 1.0 |

## Method and caveats

The runner uses the committed fake extraction provider, an in-memory tenant-
filtered retrieval fixture, deterministic safety scanning and a mock
idempotency/recovery flow. The report contains metrics and safe case references
only; it does not copy source text, prompts, provider payloads or secrets.

These are synthetic regression results, not a calibrated probability estimate
or a claim about real-world accuracy. A provider, prompt, schema or policy
change must run the full fake evaluation before release. Live evaluation is
optional, separately guarded and never required by CI.
