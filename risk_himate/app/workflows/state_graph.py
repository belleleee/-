"""LangGraph-native workflow orchestration for Risk-HiMATE.

This module upgrades the previous hand-written serial pipeline into a graph-
driven workflow. When `langgraph` is available, it builds a real StateGraph.
If the dependency is not installed yet, it falls back to a sequential runner
with the same node ordering so the repository remains runnable.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from risk_himate.app.core.schemas import PipelineState

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - compatibility fallback
    END = "__end__"
    START = "__start__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


class SequentialCompiledGraph:
    """Fallback executor that mimics the graph node order without LangGraph."""

    def __init__(
        self,
        steps: list[Callable[[PipelineState], dict[str, Any]]],
        human_review_step: Callable[[PipelineState], dict[str, Any]],
    ) -> None:
        self.steps = steps
        self.human_review_step = human_review_step

    def invoke(self, state: PipelineState | dict[str, Any]) -> dict[str, Any]:
        current = _coerce_state(state)
        for step in self.steps:
            updates = step(current)
            current = _merge_state(current, updates)
        if current.needs_human_review:
            current = _merge_state(current, self.human_review_step(current))
        return current.model_dump()


def _coerce_state(state: PipelineState | dict[str, Any]) -> PipelineState:
    if isinstance(state, dict):
        payload = state
    elif hasattr(state, "model_dump"):
        payload = state.model_dump()
    else:
        payload = dict(state)
    return PipelineState.model_validate(payload)


def _merge_state(state: PipelineState, updates: dict[str, Any]) -> PipelineState:
    payload = state.model_dump()
    payload.update(updates)
    return PipelineState.model_validate(payload)


class RiskHiMATEStateGraph:
    """Builds the graph workflow around an existing RiskHiMATEPipeline."""

    def __init__(self, pipeline: Any) -> None:
        self.pipeline = pipeline
        self.backend = "langgraph" if LANGGRAPH_AVAILABLE else "sequential_fallback"

    def compile(self):
        if not LANGGRAPH_AVAILABLE:
            return SequentialCompiledGraph(
                steps=[
                    self.pipeline._stage_prepare,
                    self.pipeline._stage_triage,
                    self.pipeline._stage_domain_analysis,
                    self.pipeline._stage_reflection,
                    self.pipeline._stage_revision,
                    self.pipeline._stage_confidence,
                    self.pipeline._stage_verifier,
                    self.pipeline._stage_finalize,
                    self.pipeline._stage_report,
                ],
                human_review_step=self.pipeline._stage_human_review,
            )

        graph = StateGraph(PipelineState)
        graph.add_node("prepare", self.pipeline._stage_prepare)
        graph.add_node("triage", self.pipeline._stage_triage)
        graph.add_node("domain_analysis", self.pipeline._stage_domain_analysis)
        graph.add_node("reflection", self.pipeline._stage_reflection)
        graph.add_node("revision", self.pipeline._stage_revision)
        graph.add_node("confidence", self.pipeline._stage_confidence)
        graph.add_node("verifier", self.pipeline._stage_verifier)
        graph.add_node("human_review", self.pipeline._stage_human_review)
        graph.add_node("finalize", self.pipeline._stage_finalize)
        graph.add_node("report", self.pipeline._stage_report)

        graph.add_edge(START, "prepare")
        graph.add_edge("prepare", "triage")
        graph.add_edge("triage", "domain_analysis")
        graph.add_edge("domain_analysis", "reflection")
        graph.add_edge("reflection", "revision")
        graph.add_edge("revision", "confidence")
        graph.add_edge("confidence", "verifier")
        graph.add_conditional_edges(
            "verifier",
            self.pipeline._route_after_verifier,
            {
                "human_review": "human_review",
                "finalize": "finalize",
            },
        )
        graph.add_edge("human_review", "finalize")
        graph.add_edge("finalize", "report")
        graph.add_edge("report", END)
        return graph.compile()
