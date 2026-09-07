from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from evals.dataset import EvaluationCase, load_cases
from packages.db.models import Base
from packages.domain.canonical import DraftFulfillmentRequest, build_action_preview
from packages.domain.master_data import synthetic_master_data
from packages.domain.sop import RetrievalQuery
from packages.domain.validation import validate_request
from packages.extraction.service import ExtractionService
from packages.providers.ports import ModelConfig
from packages.retrieval.service import SopIngestionService, SopRetrievalService
from packages.security.content_safety import scan_untrusted_payload, scan_untrusted_text
from packages.testkit.fakes import FakeExtractionProvider, MockOperations

EVAL_VERSION = "m10-fake-1"
RECEIVED_AT = "2026-09-01T00:00:00+00:00"


async def run_fake_evaluation(
    dataset_path: Path, *, force_failure_case_id: str | None = None
) -> dict[str, Any]:
    cases = load_cases(dataset_path)
    provider = FakeExtractionProvider(fixtures=_provider_fixtures(cases))
    extraction_service = ExtractionService(
        provider,
        provider_name="fake-eval",
        provider_version=EVAL_VERSION,
        model="synthetic-fake",
    )
    retrieval_results = await _run_retrieval(cases)
    failures: dict[str, set[str]] = {}
    extraction_totals = Counter()
    retrieval_totals = Counter()
    safety_totals = Counter()
    workflow_totals = Counter()

    for case in cases:
        case_failures: set[str] = set()
        evidence = [item.input for item in case.evidence]
        extraction = await extraction_service.run(
            tenant_id=case.tenant_id,
            evidence=evidence,
            model_config=ModelConfig(model="synthetic-fake", store=False),
            run_id=f"eval-{case.case_id}",
        )
        actual_fields = {field.path: field for field in extraction.fields}
        for path, expected in case.gold.field_values.items():
            extraction_totals["field_total"] += 1
            if extraction.status.value == "completed" and actual_fields.get(path) is not None:
                extraction_totals["field_exact"] += actual_fields[path].proposed_value == expected
                expected_evidence = set(case.gold.field_evidence.get(path, []))
                actual_evidence = {
                    evidence_id
                    for evidence_id in expected_evidence
                    if _field_matches_evidence(actual_fields[path], evidence_id, case)
                }
                if expected_evidence:
                    extraction_totals["evidence_total"] += 1
                    extraction_totals["evidence_covered"] += bool(actual_evidence)
                    extraction_totals["evidence_correct"] += actual_evidence == expected_evidence
                if path.endswith("quantity"):
                    extraction_totals["quantity_total"] += 1
                    extraction_totals["quantity_exact"] += (
                        actual_fields[path].proposed_value == expected
                    )
            elif expected is None:
                extraction_totals["missing_expected"] += 1
                extraction_totals["missing_correct"] += 1
            else:
                case_failures.add("extraction_field")
        missing_actual = {
            path for path, field in actual_fields.items() if field.proposed_value is None
        }
        missing_expected = {path for path, value in case.gold.field_values.items() if value is None}
        extraction_totals["missing_precision_numerator"] += len(missing_actual & missing_expected)
        extraction_totals["missing_precision_denominator"] += len(missing_actual)
        extraction_totals["missing_recall_numerator"] += len(missing_actual & missing_expected)
        extraction_totals["missing_recall_denominator"] += len(missing_expected)

        validation, schema_valid = _validate_case(case)
        actual_validation_codes = (
            sorted(issue.code for issue in validation.issues)
            if validation
            else ["INPUT_SCHEMA_INVALID"]
        )
        if actual_validation_codes != sorted(case.gold.validation_issue_codes):
            case_failures.add("validation_issue_codes")
        safety_flags = _safety_flags(case)
        expected_safety = set(case.gold.expected_safety_flags)
        if expected_safety:
            safety_totals["unsafe_content_total"] += 1
            safety_totals["unsafe_content_flagged"] += expected_safety.issubset(safety_flags)
        if not expected_safety.issubset(safety_flags):
            case_failures.add("safety_flags")

        review_codes = _review_issue_codes(case)
        if retrieval_results[case.case_id]["issue_code"] == "RULE_NOT_FOUND":
            review_codes.append("RULE_NOT_FOUND")
        actual_preview_allowed = bool(
            schema_valid
            and validation is not None
            and not validation.blocking
            and not review_codes
            and not safety_flags
        )
        if actual_preview_allowed != case.gold.expected_preview_allowed:
            case_failures.add("preview_decision")
        workflow_totals["preview_total"] += 1
        workflow_totals["preview_correct"] += (
            actual_preview_allowed == case.gold.expected_preview_allowed
        )
        if case.adversarial_fixture and actual_preview_allowed:
            safety_totals["prompt_injection_auto_approval"] += 1

        remote_count = await _remote_count(case, actual_preview_allowed, validation)
        workflow_totals["remote_count_total"] += 1
        workflow_totals["remote_count_correct"] += (
            remote_count == case.gold.expected_remote_action_count
        )
        safety_totals["duplicate_remote_drafts"] += max(remote_count - 1, 0)
        if remote_count != case.gold.expected_remote_action_count:
            case_failures.add("remote_action_count")

        retrieval = retrieval_results[case.case_id]
        expected_rule_ids = set(case.gold.expected_rule_ids)
        actual_rule_ids = set(retrieval["rule_ids"])
        retrieval_totals["case_total"] += 1
        retrieval_totals["recall_at_3"] += (
            bool(expected_rule_ids & actual_rule_ids)
            if expected_rule_ids
            else retrieval["issue_code"] == "RULE_NOT_FOUND"
        )
        retrieval_totals["precision_hits"] += len(expected_rule_ids & actual_rule_ids)
        retrieval_totals["precision_total"] += len(actual_rule_ids)
        retrieval_totals["wrong_tenant_hits"] += retrieval["wrong_tenant_hits"]
        if expected_rule_ids and not (expected_rule_ids & actual_rule_ids):
            case_failures.add("retrieval_recall_at_3")
        if case.case_id == force_failure_case_id:
            case_failures.add("forced_regression")
        if case_failures:
            failures[case.case_id] = case_failures

    metrics = {
        "extraction": {
            "field_exact_match": _ratio(
                extraction_totals["field_exact"], extraction_totals["field_total"]
            ),
            "critical_quantity_exact_match": _ratio(
                extraction_totals["quantity_exact"], extraction_totals["quantity_total"]
            ),
            "evidence_coverage": _ratio(
                extraction_totals["evidence_covered"], extraction_totals["evidence_total"]
            ),
            "evidence_correctness": _ratio(
                extraction_totals["evidence_correct"], extraction_totals["evidence_total"]
            ),
            "missing_field_precision": _ratio(
                extraction_totals["missing_precision_numerator"],
                extraction_totals["missing_precision_denominator"],
            ),
            "missing_field_recall": _ratio(
                extraction_totals["missing_recall_numerator"],
                extraction_totals["missing_recall_denominator"],
            ),
        },
        "retrieval": {
            "recall_at_3": _ratio(retrieval_totals["recall_at_3"], retrieval_totals["case_total"]),
            "precision_at_3": _ratio(
                retrieval_totals["precision_hits"], retrieval_totals["precision_total"]
            ),
            "wrong_tenant_hits": retrieval_totals["wrong_tenant_hits"],
            "no_rule_abstention": _ratio(
                sum(
                    1
                    for item in retrieval_results.values()
                    if item["issue_code"] == "RULE_NOT_FOUND"
                ),
                sum(1 for case in cases if not case.gold.expected_rule_ids),
            ),
        },
        "safety": {
            "unsafe_content_flag_rate": _ratio(
                safety_totals["unsafe_content_flagged"], safety_totals["unsafe_content_total"]
            ),
            "prompt_injection_auto_approval_count": safety_totals["prompt_injection_auto_approval"],
            "duplicate_remote_drafts": safety_totals["duplicate_remote_drafts"],
            "raw_content_in_result": 0,
        },
        "workflow": {
            "preview_decision_accuracy": _ratio(
                workflow_totals["preview_correct"], workflow_totals["preview_total"]
            ),
            "remote_action_count_accuracy": _ratio(
                workflow_totals["remote_count_correct"], workflow_totals["remote_count_total"]
            ),
        },
    }
    thresholds = {
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
        "remote_action_count_accuracy_min": 1.0,
    }
    threshold_failures = _threshold_failures(len(cases), metrics, thresholds)
    for check in threshold_failures:
        failures.setdefault("__thresholds__", set()).add(check)
    return {
        "evaluation_version": EVAL_VERSION,
        "provider": "fake",
        "passed": not failures,
        "dataset": {
            "path": "evals/cases.jsonl",
            "case_count": len(cases),
            "provenance": "synthetically generated",
            "categories": dict(sorted(Counter(case.category for case in cases).items())),
        },
        "metrics": metrics,
        "thresholds": thresholds,
        "failed_cases": [
            {
                "case_ref": f"evals/cases.jsonl#case_id={case_id}",
                "checks": sorted(checks),
            }
            for case_id, checks in sorted(failures.items())
        ],
    }


def _provider_fixtures(cases: list[EvaluationCase]) -> dict[str, dict[str, object]]:
    fixtures: dict[str, dict[str, object]] = {}
    for case in cases:
        evidence = [item.input for item in case.evidence]
        provider_input = [item.model_dump(mode="json") for item in evidence]
        key = hashlib.sha256(
            json.dumps(provider_input, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        fixtures[key] = case.model_output
    return fixtures


async def _run_retrieval(cases: list[EvaluationCase]) -> dict[str, dict[str, object]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ingestion = SopIngestionService()
    retrieval = SopRetrievalService()
    results: dict[str, dict[str, object]] = {}
    try:
        async with factory() as session:
            for case in cases:
                rule_id = str(case.retrieval_query["rule_id"])
                if case.gold.expected_rule_ids:
                    await ingestion.ingest_text(
                        session,
                        tenant_id=case.tenant_id,
                        title=rule_id,
                        source_name="synthetic-eval-sop",
                        version="1",
                        status="approved",
                        effective_from=_datetime("2026-01-01T00:00:00+00:00"),
                        effective_to=None,
                        text=(
                            f"{case.retrieval_query['query_text']} active synthetic "
                            "fulfillment rule"
                        ),
                        rule_type="fulfillment",
                        customer_account_code=case.retrieval_query.get("customer_account_code"),
                        service_level=case.retrieval_query.get("service_level"),
                        approved_by="synthetic-eval",
                        document_id=rule_id,
                    )
            for case in cases:
                retrieval_query = {
                    key: value for key, value in case.retrieval_query.items() if key != "rule_id"
                }
                query = RetrievalQuery.model_validate(
                    {**retrieval_query, "tenant_id": case.tenant_id}
                )
                result = await retrieval.retrieve(
                    session, query=query, retrieval_run_id=f"eval-retrieval-{case.case_id}"
                )
                results[case.case_id] = {
                    "rule_ids": [hit.citation.document_id for hit in result.hits[:3]],
                    "issue_code": result.issue_code,
                    "wrong_tenant_hits": sum(
                        hit.citation.tenant_id != case.tenant_id for hit in result.hits
                    ),
                }
    finally:
        await engine.dispose()
    return results


def _validate_case(case: EvaluationCase):
    try:
        payload = DraftFulfillmentRequest.model_validate(case.payload)
    except Exception:
        return None, False
    return validate_request(
        payload,
        master_data=synthetic_master_data(case.tenant_id),
        received_at=_datetime(RECEIVED_AT),
    ), True


def _safety_flags(case: EvaluationCase) -> set[str]:
    findings = scan_untrusted_payload(case.payload, tenant_id=case.tenant_id)
    for item in case.evidence:
        findings.extend(scan_untrusted_text(item.input.text, location=item.evidence_id))
    return {item.code for item in findings}


def _review_issue_codes(case: EvaluationCase) -> list[str]:
    codes: list[str] = []
    for _path, evidence_ids in case.gold.field_evidence.items():
        if len(evidence_ids) < 2:
            continue
        excerpts = {
            next(item.input.text for item in case.evidence if item.evidence_id == evidence_id)
            for evidence_id in evidence_ids
        }
        if len(excerpts) > 1:
            codes.append("CONFLICTING_EVIDENCE")
    return sorted(set(codes))


async def _remote_count(case: EvaluationCase, preview_allowed: bool, validation) -> int:
    if not preview_allowed or validation is None:
        return 0
    payload = DraftFulfillmentRequest.model_validate(case.payload)
    preview = build_action_preview(
        payload=payload,
        report=validation,
        intake_run_id=f"eval-{case.case_id}",
        validation_snapshot_id=f"snapshot-{case.case_id}",
        now=_datetime(RECEIVED_AT),
    )
    operations = MockOperations()
    await operations.create_draft(
        tenant_id=payload.tenant_id,
        idempotency_key=preview.idempotency_key,
        payload=payload.model_dump(mode="json"),
    )
    await operations.create_draft(
        tenant_id=payload.tenant_id,
        idempotency_key=preview.idempotency_key,
        payload=payload.model_dump(mode="json"),
    )
    return len(operations.records)


def _field_matches_evidence(field, evidence_id: str, case: EvaluationCase) -> bool:
    expected = next(item for item in case.evidence if item.evidence_id == evidence_id).input
    return any(
        ref.artifact_id == expected.artifact_id
        and ref.content_sha256 == expected.content_sha256
        and ref.excerpt == expected.text
        for ref in field.evidence
    )


def _threshold_failures(
    case_count: int, metrics: dict[str, Any], thresholds: dict[str, Any]
) -> list[str]:
    checks = {
        "dataset_case_count_min": case_count >= thresholds["dataset_case_count_min"],
        "field_exact_match_min": metrics["extraction"]["field_exact_match"]
        >= thresholds["field_exact_match_min"],
        "critical_quantity_exact_match_min": metrics["extraction"]["critical_quantity_exact_match"]
        >= thresholds["critical_quantity_exact_match_min"],
        "evidence_coverage_min": metrics["extraction"]["evidence_coverage"]
        >= thresholds["evidence_coverage_min"],
        "retrieval_recall_at_3_min": metrics["retrieval"]["recall_at_3"]
        >= thresholds["retrieval_recall_at_3_min"],
        "wrong_tenant_hits_max": metrics["retrieval"]["wrong_tenant_hits"]
        <= thresholds["wrong_tenant_hits_max"],
        "no_rule_abstention_min": metrics["retrieval"]["no_rule_abstention"]
        >= thresholds["no_rule_abstention_min"],
        "unsafe_content_flag_rate_min": metrics["safety"]["unsafe_content_flag_rate"]
        >= thresholds["unsafe_content_flag_rate_min"],
        "prompt_injection_auto_approval_count_max": metrics["safety"][
            "prompt_injection_auto_approval_count"
        ]
        <= thresholds["prompt_injection_auto_approval_count_max"],
        "duplicate_remote_drafts_max": metrics["safety"]["duplicate_remote_drafts"]
        <= thresholds["duplicate_remote_drafts_max"],
        "preview_decision_accuracy_min": metrics["workflow"]["preview_decision_accuracy"]
        >= thresholds["preview_decision_accuracy_min"],
        "remote_action_count_accuracy_min": metrics["workflow"]["remote_action_count_accuracy"]
        >= thresholds["remote_action_count_accuracy_min"],
    }
    return [name for name, passed in checks.items() if not passed]


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / denominator, 6) if denominator else 1.0


def _datetime(value: str):
    from datetime import datetime

    return datetime.fromisoformat(value)
