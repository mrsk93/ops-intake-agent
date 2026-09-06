from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from packages.workflow.graph import build_intake_graph, graph_config
from packages.workflow.nodes import WorkflowNodeError
from packages.workflow.state import IntakeGraphState, initial_graph_state


class ReviewRuntime:
    async def safety_check(self, *, tenant_id: str, artifact_ids: Sequence[str]) -> None:
        assert tenant_id == "tenant-a"
        assert artifact_ids == ["artifact-1"]

    async def parse_artifacts(
        self, *, tenant_id: str, artifact_ids: Sequence[str]
    ) -> list[Mapping[str, str]]:
        return [
            {
                "artifact_id": artifact_ids[0],
                "parsed_artifact_id": "parsed-1",
                "parser_version": "test-parser-1",
                "text_sha256": "a" * 64,
            }
        ]

    async def classify_document_set(
        self, *, tenant_id: str, parser_outputs: Sequence[Mapping[str, str]]
    ) -> Mapping[str, str]:
        return {"label": "booking_request", "classification_run_id": "classification-1"}

    async def extract_fields(
        self,
        *,
        tenant_id: str,
        parser_outputs: Sequence[Mapping[str, str]],
        classification: Mapping[str, str] | None,
    ) -> list[Mapping[str, str]]:
        return [
            {
                "path": "service_level",
                "status": "extracted",
                "output_hash": "b" * 64,
                "evidence_ref_ids": "evidence-1",
            }
        ]

    async def retrieve_rules(
        self,
        *,
        tenant_id: str,
        extracted_fields: Sequence[Mapping[str, str]],
    ) -> Mapping[str, object]:
        return {
            "retrieval_run_id": "retrieval-1",
            "rule_refs": ["sop-chunk-1"],
            "issue_code": None,
        }

    async def validate_draft(
        self, *, tenant_id: str, extracted_fields: Sequence[Mapping[str, str]]
    ) -> Mapping[str, object]:
        return {
            "draft_version_id": "draft-1",
            "validation_snapshot_id": "validation-1",
            "issue_ids": [],
            "route": "validated",
        }

    async def validate_review_resume(
        self, *, tenant_id: str, state: IntakeGraphState, response: Mapping[str, object]
    ) -> None:
        if response.get("action") != "acknowledge":
            raise WorkflowNodeError(
                "UNSUPPORTED_REVIEW_DECISION",
                "only acknowledgement is supported",
                kind="reviewable",
            )


@pytest.mark.asyncio
async def test_graph_pauses_with_safe_review_payload_and_resumes_after_restart() -> None:
    saver = InMemorySaver()
    runtime = ReviewRuntime()
    graph = build_intake_graph(runtime=runtime, checkpointer=saver)
    state = initial_graph_state(
        tenant_id="tenant-a", intake_run_id="run-1", artifact_ids=["artifact-1"]
    )
    config = graph_config(intake_run_id="run-1")

    paused = await graph.ainvoke(state, config=config)

    assert paused["__interrupt__"][0].value == {
        "kind": "intake_review",
        "tenant_id": "tenant-a",
        "intake_run_id": "run-1",
        "review_version": 1,
        "artifact_ids": ["artifact-1"],
        "parser_output_refs": ["parsed-1"],
        "classification": {"label": "booking_request", "classification_run_id": "classification-1"},
        "extracted_field_refs": [
            {"path": "service_level", "status": "extracted", "output_hash": "b" * 64}
        ],
        "retrieved_rule_refs": ["sop-chunk-1"],
        "validation_issue_ids": [],
        "error_code": None,
    }

    checkpoint = saver.get_tuple(config)
    assert checkpoint is not None
    checkpoint_values = checkpoint.checkpoint["channel_values"]
    checkpoint_repr = repr(checkpoint_values)
    assert "untrusted document body" not in checkpoint_repr
    assert "raw document" not in checkpoint_repr
    assert checkpoint_values["intake_run_id"] == "run-1"

    restarted_graph = build_intake_graph(runtime=runtime, checkpointer=saver)
    resumed = await restarted_graph.ainvoke(
        Command(resume={"review_version": 1, "action": "acknowledge"}), config=config
    )

    assert resumed["status"] == "review_received"
    assert resumed["approval_id"] is None
    assert resumed["proposed_action_id"] is None


@pytest.mark.asyncio
async def test_stale_review_response_cannot_continue_workflow() -> None:
    graph = build_intake_graph(runtime=ReviewRuntime(), checkpointer=InMemorySaver())
    config = graph_config(intake_run_id="run-stale")
    await graph.ainvoke(
        initial_graph_state(
            tenant_id="tenant-a", intake_run_id="run-stale", artifact_ids=["artifact-1"]
        ),
        config=config,
    )

    resumed = await graph.ainvoke(
        Command(resume={"review_version": 0, "action": "acknowledge"}), config=config
    )

    assert resumed["status"] == "review_required"
    assert resumed["error_code"] == "STALE_REVIEW_VERSION"


class UnsafeParserRuntime(ReviewRuntime):
    async def parse_artifacts(
        self, *, tenant_id: str, artifact_ids: Sequence[str]
    ) -> list[Mapping[str, str]]:
        return [{"artifact_id": artifact_ids[0], "text": "untrusted document body"}]


@pytest.mark.asyncio
async def test_unsupported_parser_content_is_not_checkpointed_or_reviewed() -> None:
    graph = build_intake_graph(runtime=UnsafeParserRuntime(), checkpointer=InMemorySaver())
    result = await graph.ainvoke(
        initial_graph_state(
            tenant_id="tenant-a", intake_run_id="run-unsafe", artifact_ids=["artifact-1"]
        ),
        config=graph_config(intake_run_id="run-unsafe"),
    )

    assert result["status"] == "failed"
    assert result["error_code"] == "UNSAFE_PARSER_STATE"
    assert "__interrupt__" not in result
