from __future__ import annotations

import argparse
from pathlib import Path

REQUIRED_RELEASE_PATHS = (
    "README.md",
    "PLAN.md",
    "docs/DATA_FLOW.md",
    "docs/MODEL_CARD.md",
    "docs/EVALUATION_REPORT.md",
    "docs/RUNBOOK.md",
    "docs/IMPLEMENTATION_STATUS.md",
    "docs/portfolio/CASE_STUDY.md",
    "docs/portfolio/DEMO_SCRIPT.md",
    "docs/portfolio/RELEASE_CHECKLIST.md",
    "docs/portfolio/assets/01-review-workspace.svg",
    "docs/portfolio/assets/02-missing-field.svg",
    "docs/portfolio/assets/03-prompt-injection-blocked.svg",
    "docs/portfolio/assets/04-action-preview.svg",
    "docs/portfolio/assets/05-timeout-recovery.svg",
    "docs/portfolio/assets/06-evaluation-report.svg",
    "docs/portfolio/assets/01-review-workspace.png",
    "docs/portfolio/assets/02-missing-field.png",
    "docs/portfolio/assets/03-prompt-injection-blocked.png",
    "docs/portfolio/assets/04-action-preview.png",
    "docs/portfolio/assets/05-timeout-recovery.png",
    "docs/portfolio/assets/06-evaluation-report.png",
    "docs/portfolio/assets/demo.webm",
    "scripts/demo_injection.py",
    "scripts/demo_timeout_recovery.py",
)


def missing_release_paths(root: Path) -> list[str]:
    return [path for path in REQUIRED_RELEASE_PATHS if not (root / path).is_file()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the reproducible portfolio release tree.")
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    missing = missing_release_paths(args.root.resolve())
    if missing:
        print("Release rehearsal failed; missing:")
        print("\n".join(missing))
        raise SystemExit(1)
    print(f"Release rehearsal passed: {len(REQUIRED_RELEASE_PATHS)} required artifacts present.")


if __name__ == "__main__":
    main()
