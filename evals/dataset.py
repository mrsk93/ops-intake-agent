from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from packages.domain.extraction import EvidenceInput


class CaseEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=120)
    input: EvidenceInput


class GoldLabels(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_class: str
    field_values: dict[str, object]
    field_evidence: dict[str, list[str]]
    validation_issue_codes: list[str]
    review_issue_codes: list[str]
    expected_rule_ids: list[str]
    expected_preview_allowed: bool
    expected_remote_action_count: int = Field(ge=0, le=1)
    expected_safety_flags: list[str]


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(pattern=r"^[a-z0-9-]+$")
    category: str
    provenance: str
    license: str
    tenant_id: str
    adversarial_fixture: str | None = None
    evidence: list[CaseEvidence] = Field(min_length=1)
    payload: dict[str, object]
    model_output: dict[str, object]
    retrieval_query: dict[str, object]
    gold: GoldLabels


def load_cases(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            cases.append(EvaluationCase.model_validate_json(line))
        except Exception as exc:
            raise ValueError(f"invalid evaluation case at line {line_number}") from exc
    if not cases:
        raise ValueError("evaluation dataset is empty")
    return cases
