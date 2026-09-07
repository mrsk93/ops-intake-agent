import json
from pathlib import Path

import pytest

from evals.dataset import load_cases
from evals.runner import run_fake_evaluation

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals" / "cases.jsonl"


def test_dataset_has_clear_provenance_and_required_composition() -> None:
    cases = load_cases(DATASET)

    assert len(cases) >= 60
    assert {case.provenance for case in cases} == {"synthetically generated"}
    assert {case.license for case in cases} == {"synthetic-internal"}
    assert {case.category for case in cases} >= {
        "clean_digital",
        "tabular",
        "scanned_noisy",
        "conflict_amendment",
        "missing_ambiguous",
        "adversarial",
    }
    assert len({case.case_id for case in cases}) == len(cases)
    assert {case.adversarial_fixture for case in cases if case.adversarial_fixture} >= {
        "ignore_previous_approve",
        "call_createshipment",
        "white_on_white_pdf_injection",
        "sop_like_customer_text",
        "cross_tenant_collision",
        "unicode_lookalike",
        "negative_or_decimal_quantity",
        "conflicting_date_formats",
        "spreadsheet_formula",
        "pdf_embedded_link_attachment",
    }


@pytest.mark.asyncio
async def test_fake_evaluation_is_reproducible_and_thresholds_pass() -> None:
    first = await run_fake_evaluation(DATASET)
    second = await run_fake_evaluation(DATASET)

    assert first["passed"] is True
    assert first["metrics"] == second["metrics"]
    assert first["thresholds"] == second["thresholds"]
    assert first["failed_cases"] == []
    assert first["dataset"]["case_count"] >= 60


@pytest.mark.asyncio
async def test_evaluation_failures_reference_case_ids_without_content() -> None:
    result = await run_fake_evaluation(DATASET, force_failure_case_id="adv-001")

    assert result["passed"] is False
    assert result["failed_cases"][0]["case_ref"].startswith("evals/cases.jsonl#case_id=")
    serialized = json.dumps(result)
    assert "IGNORE PREVIOUS" not in serialized
    assert "CUSTOMER" not in serialized
