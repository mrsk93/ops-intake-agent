from __future__ import annotations

import re
from pathlib import Path

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
_IGNORED_PARTS = {".git", ".venv", "node_modules", ".next", ".pytest_cache", ".ruff_cache"}
_TEXT_SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".json", ".jsonl", ".ts", ".tsx"}


def scan_repository(root: Path) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in _IGNORED_PARTS for part in path.parts):
            continue
        if path.suffix in _TEXT_SUFFIXES:
            text = path.read_text(errors="ignore")
            for pattern in _SECRET_PATTERNS:
                if pattern.search(text):
                    findings.append(f"secret-pattern:{path}")
                    break
    compose = root / "docker-compose.yml"
    if compose.exists() and re.search(r"image:\s*[^\s]+:latest\b", compose.read_text()):
        findings.append(f"floating-container-tag:{compose}")
    for required in (root / "uv.lock", root / "pnpm-lock.yaml"):
        if not required.exists():
            findings.append(f"missing-lockfile:{required}")
    return sorted(findings)


if __name__ == "__main__":
    findings = scan_repository(Path("."))
    if findings:
        print("Security scan failed:")
        print("\n".join(findings))
        raise SystemExit(1)
    print(
        "Security scan passed: no tracked secret pattern, floating container tag, "
        "or missing lockfile."
    )
