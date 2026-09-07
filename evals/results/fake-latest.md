# Synthetic Evaluation Report

- Evaluation version: `m10-fake-1`
- Provider: `fake`
- Status: **PASS**
- Dataset: `evals/cases.jsonl` (66 cases)
- Provenance: synthetic fixtures only

## Metrics

| Area | Metric | Value |
| --- | --- | ---: |
| extraction | field_exact_match | 1.0 |
| extraction | critical_quantity_exact_match | 1.0 |
| extraction | evidence_coverage | 1.0 |
| extraction | evidence_correctness | 1.0 |
| extraction | missing_field_precision | 1.0 |
| extraction | missing_field_recall | 1.0 |
| retrieval | recall_at_3 | 1.0 |
| retrieval | precision_at_3 | 0.336788 |
| retrieval | wrong_tenant_hits | 0 |
| retrieval | no_rule_abstention | 1.0 |
| safety | unsafe_content_flag_rate | 1.0 |
| safety | prompt_injection_auto_approval_count | 0 |
| safety | duplicate_remote_drafts | 0 |
| safety | raw_content_in_result | 0 |
| workflow | preview_decision_accuracy | 1.0 |
| workflow | remote_action_count_accuracy | 1.0 |

## Thresholds

```json
{
  "dataset_case_count_min": 60,
  "field_exact_match_min": 0.99,
  "critical_quantity_exact_match_min": 1.0,
  "evidence_coverage_min": 1.0,
  "retrieval_recall_at_3_min": 1.0,
  "wrong_tenant_hits_max": 0,
  "no_rule_abstention_min": 1.0,
  "unsafe_content_flag_rate_min": 1.0,
  "prompt_injection_auto_approval_count_max": 0,
  "duplicate_remote_drafts_max": 0,
  "preview_decision_accuracy_min": 1.0,
  "remote_action_count_accuracy_min": 1.0
}
```

No failing cases. The report stores only safe case references and metrics.
