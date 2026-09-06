from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source_files() -> list[Path]:
    ignored = {".git", ".venv", "node_modules", ".next", ".pytest_cache", ".ruff_cache"}
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in ignored for part in path.parts)
        and path.suffix in {".py", ".md", ".toml", ".env", ".yml", ".yaml"}
    ]


def test_plan_and_adr_sources_contain_no_real_client_material() -> None:
    tracked_text = "\n".join(path.read_text() for path in source_files())
    forbidden_key_prefix = "OPENAI_API_KEY=" + "sk-"
    assert forbidden_key_prefix not in tracked_text
    assert (
        "chain-of-thought" not in tracked_text.lower()
        or "never store or display chain-of-thought" in tracked_text.lower()
    )


def test_domain_does_not_import_frameworks_or_provider_sdks() -> None:
    domain_text = "\n".join(
        path.read_text() for path in (ROOT / "packages" / "domain").glob("*.py")
    )
    for forbidden in ("fastapi", "langgraph", "openai", "sqlalchemy", "redis"):
        assert forbidden not in domain_text.lower()
