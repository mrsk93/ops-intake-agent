from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from packages.workflow.nodes import (
    WorkflowRuntime,
    calculate_review_route,
    classify_document_set,
    extract_fields,
    interrupt_for_review,
    parse_artifacts,
    register_intake,
    retrieve_tenant_rules,
    safety_check_artifacts,
    validate_draft,
)
from packages.workflow.state import IntakeGraphState


def build_intake_graph(*, runtime: WorkflowRuntime, checkpointer: Any):
    builder = StateGraph(IntakeGraphState)
    builder.add_node("register_intake", _bind(register_intake, runtime))
    builder.add_node("safety_check_artifacts", _bind(safety_check_artifacts, runtime))
    builder.add_node("parse_artifacts", _bind(parse_artifacts, runtime))
    builder.add_node("classify_document_set", _bind(classify_document_set, runtime))
    builder.add_node("extract_fields", _bind(extract_fields, runtime))
    builder.add_node("retrieve_tenant_rules", _bind(retrieve_tenant_rules, runtime))
    builder.add_node("validate_draft", _bind(validate_draft, runtime))
    builder.add_node("calculate_review_route", _bind(calculate_review_route, runtime))
    builder.add_node("interrupt_for_review", _bind(interrupt_for_review, runtime))
    builder.add_edge(START, "register_intake")
    builder.add_edge("register_intake", "safety_check_artifacts")
    builder.add_edge("safety_check_artifacts", "parse_artifacts")
    builder.add_edge("parse_artifacts", "classify_document_set")
    builder.add_edge("classify_document_set", "extract_fields")
    builder.add_edge("extract_fields", "retrieve_tenant_rules")
    builder.add_edge("retrieve_tenant_rules", "validate_draft")
    builder.add_edge("validate_draft", "calculate_review_route")
    builder.add_edge("calculate_review_route", "interrupt_for_review")
    builder.add_edge("interrupt_for_review", END)
    return builder.compile(checkpointer=checkpointer)


def _bind(node, runtime: WorkflowRuntime):
    async def bound(state: IntakeGraphState):
        return await node(state, runtime=runtime)

    return bound


def graph_config(*, intake_run_id: str) -> dict[str, dict[str, str]]:
    if not intake_run_id or len(intake_run_id) > 255:
        raise ValueError("intake_run_id must be a non-empty value under 255 characters")
    return {"configurable": {"thread_id": intake_run_id}}
