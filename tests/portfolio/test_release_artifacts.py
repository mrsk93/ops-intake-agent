from __future__ import annotations

import json
from pathlib import Path

from scripts.demo_injection import run_demo as run_injection_demo
from scripts.demo_timeout_recovery import run_demo as run_recovery_demo
from scripts.rehearse_release import REQUIRED_RELEASE_PATHS

ROOT = Path(__file__).resolve().parents[2]


def test_portfolio_release_contract_has_required_docs_and_assets() -> None:
    missing = [path for path in REQUIRED_RELEASE_PATHS if not (ROOT / path).exists()]

    assert missing == []
    screenshots = sorted((ROOT / "docs/portfolio/assets").glob("*.svg"))
    assert len(screenshots) == 6
    for screenshot in screenshots:
        assert "synthetic" in screenshot.read_text().lower()
    assert (ROOT / "docs/portfolio/assets/demo.webm").stat().st_size > 0
    browser_captures = sorted((ROOT / "docs/portfolio/assets").glob("*.png"))
    assert len(browser_captures) == 6
    assert all(capture.stat().st_size > 0 for capture in browser_captures)


def test_stable_evaluation_report_matches_committed_result() -> None:
    result = json.loads((ROOT / "evals/results/fake-latest.json").read_text())
    report = (ROOT / "docs/EVALUATION_REPORT.md").read_text()

    assert result["passed"] is True
    assert f"{result['dataset']['case_count']} cases" in report
    assert result["evaluation_version"] in report
    assert "Precision@3" in report
    assert "synthetic" in report.lower()


def test_injection_demo_is_blocked_without_operational_side_effects() -> None:
    result = run_injection_demo()

    assert result == {
        "fixture": "ignore_previous_approve",
        "status": "blocked_for_review",
        "preview_allowed": False,
        "operational_write_count": 0,
    }


def test_timeout_demo_recovers_one_remote_draft() -> None:
    result = run_recovery_demo()

    assert result == {
        "status": "verified_after_lookup",
        "create_calls": 1,
        "remote_record_count": 1,
        "read_back_verified": True,
    }
