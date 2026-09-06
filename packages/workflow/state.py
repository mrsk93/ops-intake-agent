from __future__ import annotations

from typing import Literal, TypedDict


class IntakeGraphState(TypedDict):
    """Checkpoint-safe state: identifiers, hashes, versions and concise decisions only."""

    tenant_id: str
    intake_run_id: str
    artifact_ids: list[str]
    parser_outputs: list[dict[str, str]]
    document_classification: dict[str, str] | None
    extracted_fields: list[dict[str, str]]
    retrieved_rule_refs: list[str]
    retrieval_run_id: str | None
    validation_issue_ids: list[str]
    validation_snapshot_id: str | None
    draft_version_id: str | None
    review_version: int
    proposed_action_id: str | None
    approval_id: str | None
    execution_receipt_id: str | None
    status: Literal[
        "received",
        "safety_checked",
        "parsed",
        "classified",
        "extracted",
        "rules_retrieved",
        "validated",
        "review_required",
        "review_received",
        "failed",
    ]
    error_code: str | None


def initial_graph_state(
    *, tenant_id: str, intake_run_id: str, artifact_ids: list[str]
) -> IntakeGraphState:
    return {
        "tenant_id": tenant_id,
        "intake_run_id": intake_run_id,
        "artifact_ids": list(artifact_ids),
        "parser_outputs": [],
        "document_classification": None,
        "extracted_fields": [],
        "retrieved_rule_refs": [],
        "retrieval_run_id": None,
        "validation_issue_ids": [],
        "validation_snapshot_id": None,
        "draft_version_id": None,
        "review_version": 1,
        "proposed_action_id": None,
        "approval_id": None,
        "execution_receipt_id": None,
        "status": "received",
        "error_code": None,
    }
