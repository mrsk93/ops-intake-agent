from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from langgraph.types import interrupt

from packages.workflow.state import IntakeGraphState

WorkflowErrorKind = Literal["retryable", "reviewable", "terminal"]


class WorkflowNodeError(ValueError):
    def __init__(self, code: str, message: str, *, kind: WorkflowErrorKind) -> None:
        super().__init__(message)
        self.code = code
        self.kind = kind


class WorkflowRuntime(Protocol):
    async def safety_check(self, *, tenant_id: str, artifact_ids: Sequence[str]) -> None: ...

    async def parse_artifacts(
        self, *, tenant_id: str, artifact_ids: Sequence[str]
    ) -> list[Mapping[str, str]]: ...

    async def classify_document_set(
        self, *, tenant_id: str, parser_outputs: Sequence[Mapping[str, str]]
    ) -> Mapping[str, str]: ...

    async def extract_fields(
        self,
        *,
        tenant_id: str,
        parser_outputs: Sequence[Mapping[str, str]],
        classification: Mapping[str, str] | None,
    ) -> list[Mapping[str, str]]: ...

    async def retrieve_rules(
        self,
        *,
        tenant_id: str,
        extracted_fields: Sequence[Mapping[str, str]],
    ) -> Mapping[str, object]: ...

    async def validate_draft(
        self, *, tenant_id: str, extracted_fields: Sequence[Mapping[str, str]]
    ) -> Mapping[str, object]: ...

    async def validate_review_resume(
        self, *, tenant_id: str, state: IntakeGraphState, response: Mapping[str, object]
    ) -> None: ...


@dataclass(frozen=True)
class DeterministicWorkflowRuntime:
    """Provider-free runtime that emits only references and reviewable abstentions."""

    async def safety_check(self, *, tenant_id: str, artifact_ids: Sequence[str]) -> None:
        del tenant_id
        if not artifact_ids:
            raise WorkflowNodeError(
                "NO_ARTIFACTS", "an intake needs at least one artifact", kind="reviewable"
            )

    async def parse_artifacts(
        self, *, tenant_id: str, artifact_ids: Sequence[str]
    ) -> list[Mapping[str, str]]:
        del tenant_id
        return [
            {
                "artifact_id": artifact_id,
                "parsed_artifact_id": f"parsed:{artifact_id}",
                "parser_version": "deterministic-ref-1",
            }
            for artifact_id in artifact_ids
        ]

    async def classify_document_set(
        self, *, tenant_id: str, parser_outputs: Sequence[Mapping[str, str]]
    ) -> Mapping[str, str]:
        del tenant_id
        return {
            "label": "booking_request",
            "classification_run_id": f"classification:{len(parser_outputs)}",
        }

    async def extract_fields(
        self,
        *,
        tenant_id: str,
        parser_outputs: Sequence[Mapping[str, str]],
        classification: Mapping[str, str] | None,
    ) -> list[Mapping[str, str]]:
        del tenant_id, parser_outputs, classification
        return []

    async def retrieve_rules(
        self,
        *,
        tenant_id: str,
        extracted_fields: Sequence[Mapping[str, str]],
    ) -> Mapping[str, object]:
        del tenant_id, extracted_fields
        return {"retrieval_run_id": None, "rule_refs": [], "issue_code": "RULE_NOT_FOUND"}

    async def validate_draft(
        self, *, tenant_id: str, extracted_fields: Sequence[Mapping[str, str]]
    ) -> Mapping[str, object]:
        del tenant_id, extracted_fields
        return {
            "draft_version_id": None,
            "validation_snapshot_id": None,
            "issue_ids": ["DRAFT_NOT_AVAILABLE"],
            "route": "blocked",
        }

    async def validate_review_resume(
        self, *, tenant_id: str, state: IntakeGraphState, response: Mapping[str, object]
    ) -> None:
        del tenant_id, state
        if response.get("action") != "acknowledge":
            raise WorkflowNodeError(
                "UNSUPPORTED_REVIEW_DECISION",
                "review response must acknowledge the persisted review payload",
                kind="reviewable",
            )


async def register_intake(
    state: IntakeGraphState, *, runtime: WorkflowRuntime
) -> dict[str, object]:
    del runtime
    if not state.get("tenant_id") or not state.get("intake_run_id"):
        return _failure("INVALID_INTAKE_CONTEXT", kind="terminal")
    return {"status": "received", "error_code": None}


async def safety_check_artifacts(
    state: IntakeGraphState, *, runtime: WorkflowRuntime
) -> dict[str, object]:
    if _stopped(state):
        return {}
    try:
        await runtime.safety_check(tenant_id=state["tenant_id"], artifact_ids=state["artifact_ids"])
    except WorkflowNodeError as exc:
        return _failure(exc.code, kind=exc.kind)
    return {"status": "safety_checked", "error_code": None}


async def parse_artifacts(
    state: IntakeGraphState, *, runtime: WorkflowRuntime
) -> dict[str, object]:
    if _stopped(state):
        return {}
    try:
        outputs = await runtime.parse_artifacts(
            tenant_id=state["tenant_id"], artifact_ids=state["artifact_ids"]
        )
        safe_outputs = [_safe_parser_output(output) for output in outputs]
    except WorkflowNodeError as exc:
        return _failure(exc.code, kind=exc.kind)
    return {"parser_outputs": safe_outputs, "status": "parsed", "error_code": None}


async def classify_document_set(
    state: IntakeGraphState, *, runtime: WorkflowRuntime
) -> dict[str, object]:
    if _stopped(state):
        return {}
    try:
        classification = await runtime.classify_document_set(
            tenant_id=state["tenant_id"], parser_outputs=state["parser_outputs"]
        )
        safe_classification = _safe_classification(classification)
    except WorkflowNodeError as exc:
        return _failure(exc.code, kind=exc.kind)
    return {"document_classification": safe_classification, "status": "classified"}


async def extract_fields(state: IntakeGraphState, *, runtime: WorkflowRuntime) -> dict[str, object]:
    if _stopped(state):
        return {}
    try:
        fields = await runtime.extract_fields(
            tenant_id=state["tenant_id"],
            parser_outputs=state["parser_outputs"],
            classification=state["document_classification"],
        )
        safe_fields = [_safe_extracted_field(field) for field in fields]
    except WorkflowNodeError as exc:
        return _failure(exc.code, kind=exc.kind)
    return {"extracted_fields": safe_fields, "status": "extracted"}


async def retrieve_tenant_rules(
    state: IntakeGraphState, *, runtime: WorkflowRuntime
) -> dict[str, object]:
    if _stopped(state):
        return {}
    try:
        result = await runtime.retrieve_rules(
            tenant_id=state["tenant_id"], extracted_fields=state["extracted_fields"]
        )
        retrieval_run_id = _optional_string(result.get("retrieval_run_id"))
        rule_refs = _string_list(result.get("rule_refs"))
        issue_code = _optional_string(result.get("issue_code"))
    except WorkflowNodeError as exc:
        return _failure(exc.code, kind=exc.kind)
    return {
        "retrieval_run_id": retrieval_run_id,
        "retrieved_rule_refs": rule_refs,
        "status": "review_required" if issue_code else "rules_retrieved",
        "error_code": issue_code,
    }


async def validate_draft(state: IntakeGraphState, *, runtime: WorkflowRuntime) -> dict[str, object]:
    if _stopped(state):
        return {}
    try:
        result = await runtime.validate_draft(
            tenant_id=state["tenant_id"], extracted_fields=state["extracted_fields"]
        )
        route = result.get("route")
        if route not in {"validated", "needs_review", "blocked"}:
            raise WorkflowNodeError(
                "INVALID_VALIDATION_ROUTE", "validation route is invalid", kind="terminal"
            )
        issue_ids = _string_list(result.get("issue_ids"))
    except WorkflowNodeError as exc:
        return _failure(exc.code, kind=exc.kind)
    return {
        "draft_version_id": _optional_string(result.get("draft_version_id")),
        "validation_snapshot_id": _optional_string(result.get("validation_snapshot_id")),
        "validation_issue_ids": issue_ids,
        "status": "review_required",
        "error_code": issue_ids[0] if issue_ids else state.get("error_code"),
    }


async def calculate_review_route(
    state: IntakeGraphState, *, runtime: WorkflowRuntime
) -> dict[str, object]:
    del runtime
    if _stopped(state):
        return {}
    return {"status": "review_required"}


async def interrupt_for_review(
    state: IntakeGraphState, *, runtime: WorkflowRuntime
) -> dict[str, object]:
    if _stopped(state):
        return {}
    payload = {
        "kind": "intake_review",
        "tenant_id": state["tenant_id"],
        "intake_run_id": state["intake_run_id"],
        "review_version": state["review_version"],
        "artifact_ids": list(state["artifact_ids"]),
        "parser_output_refs": [item["parsed_artifact_id"] for item in state["parser_outputs"]],
        "classification": state["document_classification"],
        "extracted_field_refs": [
            {key: field[key] for key in ("path", "status", "output_hash") if key in field}
            for field in state["extracted_fields"]
        ],
        "retrieved_rule_refs": list(state["retrieved_rule_refs"]),
        "validation_issue_ids": list(state["validation_issue_ids"]),
        "error_code": state["error_code"],
    }
    response = interrupt(payload)
    if not isinstance(response, Mapping):
        return _failure("INVALID_REVIEW_RESPONSE", kind="reviewable")
    if response.get("review_version") != state["review_version"]:
        return _failure("STALE_REVIEW_VERSION", kind="reviewable")
    try:
        await runtime.validate_review_resume(
            tenant_id=state["tenant_id"], state=state, response=response
        )
    except WorkflowNodeError as exc:
        return _failure(exc.code, kind=exc.kind)
    return {"status": "review_received", "error_code": None}


def _stopped(state: IntakeGraphState) -> bool:
    return state["status"] == "failed"


def _failure(code: str, *, kind: WorkflowErrorKind) -> dict[str, object]:
    return {
        "status": "review_required" if kind == "reviewable" else "failed",
        "error_code": code,
    }


def _safe_parser_output(output: Mapping[str, str]) -> dict[str, str]:
    allowed = {
        "artifact_id",
        "parsed_artifact_id",
        "parser_version",
        "text_sha256",
        "warning_count",
    }
    return _safe_string_mapping(output, allowed=allowed, code="UNSAFE_PARSER_STATE")


def _safe_classification(output: Mapping[str, str]) -> dict[str, str]:
    allowed = {"label", "classification_run_id", "output_hash", "decision_code"}
    return _safe_string_mapping(output, allowed=allowed, code="UNSAFE_CLASSIFICATION_STATE")


def _safe_extracted_field(output: Mapping[str, str]) -> dict[str, str]:
    allowed = {"path", "status", "output_hash", "evidence_ref_ids", "extractor_version"}
    return _safe_string_mapping(output, allowed=allowed, code="UNSAFE_EXTRACTION_STATE")


def _safe_string_mapping(
    output: Mapping[str, str], *, allowed: set[str], code: str
) -> dict[str, str]:
    if not isinstance(output, Mapping) or not set(output).issubset(allowed):
        raise WorkflowNodeError(
            code, "workflow state contains unsupported content", kind="terminal"
        )
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in output.items()):
        raise WorkflowNodeError(code, "workflow state references must be strings", kind="terminal")
    return dict(output)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise WorkflowNodeError(
            "INVALID_WORKFLOW_REFERENCE", "workflow reference must be a string", kind="terminal"
        )
    return value


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise WorkflowNodeError(
            "INVALID_WORKFLOW_REFERENCE_LIST",
            "workflow references must be strings",
            kind="terminal",
        )
    return list(value)
