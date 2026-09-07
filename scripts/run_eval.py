from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from evals.report import write_report
from evals.runner import run_fake_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the synthetic Ops Intake evaluation.")
    parser.add_argument("--provider", choices=("fake", "live"), default="fake")
    parser.add_argument("--dataset", type=Path, default=Path("evals/cases.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("evals/results"))
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--max-cost-usd", type=float, default=None)
    args = parser.parse_args()
    if args.provider == "live":
        if not args.allow_live:
            raise SystemExit("live evaluation requires --allow-live")
        if not os.environ.get("OPENAI_API_KEY") or not os.environ.get("OPENAI_MODEL"):
            raise SystemExit("live evaluation requires OPENAI_API_KEY and OPENAI_MODEL")
        if args.max_cases is None or args.max_cases < 1 or args.max_cases > 20:
            raise SystemExit("live evaluation requires --max-cases between 1 and 20")
        if args.max_cost_usd is None or args.max_cost_usd <= 0:
            raise SystemExit("live evaluation requires a positive --max-cost-usd guard")
        raise SystemExit(
            "live evaluation is intentionally opt-in and not implemented in the fake CI runner; "
            "use the provider port with the same case and cost guard"
        )
    result = asyncio.run(run_fake_evaluation(args.dataset))
    json_path, markdown_path = write_report(result, args.output_dir)
    print(f"Evaluation {'passed' if result['passed'] else 'failed'}.")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
