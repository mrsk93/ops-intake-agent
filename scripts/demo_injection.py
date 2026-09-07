from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.dataset import load_cases
from packages.security.content_safety import scan_untrusted_payload


def run_demo() -> dict[str, Any]:
    """Run the synthetic prompt-injection story without any provider or write."""

    cases = load_cases(Path("evals/cases.jsonl"))
    case = next(item for item in cases if item.adversarial_fixture == "ignore_previous_approve")
    findings = scan_untrusted_payload(case.payload, tenant_id=case.tenant_id)
    blocked = {finding.code for finding in findings} >= {"INSTRUCTION_LIKE_CONTENT"}
    return {
        "fixture": case.adversarial_fixture,
        "status": "blocked_for_review" if blocked else "unexpectedly_unblocked",
        "preview_allowed": case.gold.expected_preview_allowed and not blocked,
        "operational_write_count": 0,
    }


def main() -> None:
    result = run_demo()
    print(json.dumps(result, sort_keys=True))
    if result["status"] != "blocked_for_review" or result["operational_write_count"] != 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
