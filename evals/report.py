from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_report(result: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "fake-latest.json"
    markdown_path = output_dir / "fake-latest.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    markdown_path.write_text(render_markdown(result))
    return json_path, markdown_path


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Synthetic Evaluation Report",
        "",
        f"- Evaluation version: `{result['evaluation_version']}`",
        f"- Provider: `{result['provider']}`",
        f"- Status: **{'PASS' if result['passed'] else 'FAIL'}**",
        f"- Dataset: `{result['dataset']['path']}` ({result['dataset']['case_count']} cases)",
        "- Provenance: synthetic fixtures only",
        "",
        "## Metrics",
        "",
        "| Area | Metric | Value |",
        "| --- | --- | ---: |",
    ]
    for area, metrics in result["metrics"].items():
        for name, value in metrics.items():
            lines.append(f"| {area} | {name} | {value} |")
    lines.extend(
        ["", "## Thresholds", "", "```json", json.dumps(result["thresholds"], indent=2), "```", ""]
    )
    if result["failed_cases"]:
        lines.extend(["## Failing case references", ""])
        for item in result["failed_cases"]:
            lines.append(f"- `{item['case_ref']}`: {', '.join(item['checks'])}")
    else:
        lines.extend(
            ["No failing cases. The report stores only safe case references and metrics.", ""]
        )
    return "\n".join(lines)
