"""Pipeline orchestration for Step 1 and Step 2."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, UTC
from typing import Any

from risk_himate.app.agents.domain_agents import (
    AlgorithmSafetyAgent,
    DataComplianceAgent,
    GeopoliticalRiskAgent,
    IPRiskAgent,
    TechEthicsAgent,
)
from risk_himate.app.data_sources.base import CompanyDataCollector
from risk_himate.app.data_sources.company_profile_collector import LocalCompanyDataCollector
from risk_himate.app.data_sources.external_api_collector import ExternalCompanyDataCollector
from risk_himate.app.agents.reflection_agent import ReflectionAgent
from risk_himate.app.agents.revision_agent import RevisionAgent
from risk_himate.app.agents.triage_agent import TriageAgent
from risk_himate.app.agents.verifier_agent import VerifierAgent
from risk_himate.app.core.analysis import (
    flatten_findings,
)
from risk_himate.app.core.chunking import chunk_text
from risk_himate.app.core.confidence import ConfidenceEvaluator
from risk_himate.app.core.reporting import build_risk_report
from risk_himate.app.core.schemas import AnalysisInput, PipelineState, RiskFinding, TextChunk, TriageResult
from risk_himate.app.core.taxonomy import CATEGORY_PROPAGATION_MAP
from risk_himate.app.llm.client import OpenAICompatibleLLMClient
from risk_himate.app.rag.recommendation_store import LocalRecommendationStore, RecommendationStore
from risk_himate.app.storage.history_store import HistoryStore, NullHistoryStore, compute_trend
from risk_himate.app.workflows.state_graph import RiskHiMATEStateGraph


class RiskHiMATEPipeline:
    def __init__(
        self,
        recommendation_store: RecommendationStore | None = None,
        history_store: HistoryStore | None = None,
        company_data_collector: CompanyDataCollector | None = None,
        llm_client: OpenAICompatibleLLMClient | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.triage_agent = TriageAgent(llm_client=llm_client)
        self.domain_agents = [
            AlgorithmSafetyAgent(llm_client=llm_client),
            DataComplianceAgent(llm_client=llm_client),
            TechEthicsAgent(llm_client=llm_client),
            IPRiskAgent(llm_client=llm_client),
            GeopoliticalRiskAgent(llm_client=llm_client),
        ]
        self.reflection_agent = ReflectionAgent(llm_client=llm_client)
        self.revision_agent = RevisionAgent(llm_client=llm_client)
        self.confidence_evaluator = ConfidenceEvaluator()
        self.verifier_agent = VerifierAgent(llm_client=llm_client)
        self.recommendation_store = recommendation_store or LocalRecommendationStore()
        self.history_store = history_store or NullHistoryStore()
        self.company_data_collector = company_data_collector or ExternalCompanyDataCollector.from_env(
            fallback_collector=LocalCompanyDataCollector()
        )
        self.workflow = RiskHiMATEStateGraph(self)
        self.compiled_workflow = self.workflow.compile()
        self.workflow_backend = self.workflow.backend

    def run_state(self, analysis_input: AnalysisInput) -> PipelineState:
        state = PipelineState(
            analysis_input=analysis_input,
            timestamp=datetime.now(UTC).isoformat(),
        )
        result = self.compiled_workflow.invoke(state.model_dump())
        final_state = PipelineState.model_validate(result)
        if final_state.risk_report is None:
            raise ValueError("Risk report generation failed.")
        self.history_store.save_report(final_state.risk_report)
        return final_state

    def _stage_prepare(self, state: PipelineState | dict[str, Any]) -> dict[str, Any]:
        state = self._coerce_state(state)
        analysis_input = self._normalize_input(state.analysis_input)
        if not analysis_input.raw_text:
            raise ValueError("Analysis input must include raw_text after normalization.")
        chunks = chunk_text(analysis_input.raw_text)
        return {
            "analysis_input": analysis_input.model_dump(),
            "timestamp": state.timestamp or datetime.now(UTC).isoformat(),
            "chunks": [chunk.model_dump() for chunk in chunks],
        }

    def _stage_triage(self, state: PipelineState | dict[str, Any]) -> dict[str, Any]:
        state = self._coerce_state(state)
        triage_results = self.triage_agent.analyze(state.chunks)
        return {
            "triage_results": [result.model_dump() for result in triage_results],
        }

    def _stage_domain_analysis(self, state: PipelineState | dict[str, Any]) -> dict[str, Any]:
        state = self._coerce_state(state)
        chunks_by_id = {chunk.chunk_id: chunk for chunk in state.chunks}
        findings_by_category = self._run_domain_agents(state.triage_results, chunks_by_id)
        return {
            "domain_findings": {
                category: [finding.model_dump() for finding in findings]
                for category, findings in findings_by_category.items()
            }
        }

    def _stage_reflection(self, state: PipelineState | dict[str, Any]) -> dict[str, Any]:
        state = self._coerce_state(state)
        reflection_result = self.reflection_agent.analyze(state)
        return {"reflection_result": reflection_result.model_dump()}

    def _stage_revision(self, state: PipelineState | dict[str, Any]) -> dict[str, Any]:
        state = self._coerce_state(state)
        revised_findings = self.revision_agent.revise(state)
        return {
            "revised_findings": {
                category: [finding.model_dump() for finding in findings]
                for category, findings in revised_findings.items()
            }
        }

    def _stage_confidence(self, state: PipelineState | dict[str, Any]) -> dict[str, Any]:
        state = self._coerce_state(state)
        confidence_result = self.confidence_evaluator.evaluate(state)
        return {"confidence_result": confidence_result.model_dump()}

    def _stage_verifier(self, state: PipelineState | dict[str, Any]) -> dict[str, Any]:
        state = self._coerce_state(state)
        verification_result = self.verifier_agent.verify(state)
        return {"verification_result": verification_result.model_dump()}

    def _stage_human_review(self, state: PipelineState | dict[str, Any]) -> dict[str, Any]:
        state = self._coerce_state(state)
        return {
            "needs_human_review": True,
        }

    def _stage_finalize(self, state: PipelineState | dict[str, Any]) -> dict[str, Any]:
        state = self._coerce_state(state)
        verification_result = state.verification_result
        final_findings = self._resolve_final_findings(state)
        needs_human_review = bool(verification_result and verification_result.needs_human_review) or state.needs_human_review
        return {
            "final_findings": [finding.model_dump() for finding in final_findings],
            "needs_human_review": needs_human_review,
        }

    def _stage_report(self, state: PipelineState | dict[str, Any]) -> dict[str, Any]:
        state = self._coerce_state(state)
        report = self._build_report(state)
        return {"risk_report": report.model_dump()}

    def _route_after_verifier(self, state: PipelineState | dict[str, Any]) -> str:
        state = self._coerce_state(state)
        if state.verification_result and state.verification_result.needs_human_review:
            return "human_review"
        return "finalize"

    def _coerce_state(self, state: PipelineState | dict[str, Any]) -> PipelineState:
        if isinstance(state, dict):
            payload = state
        elif hasattr(state, "model_dump"):
            payload = state.model_dump()
        else:
            payload = dict(state)
        return PipelineState.model_validate(payload)

    def _run_domain_agents(
        self,
        triage_results: list[TriageResult],
        chunks_by_id: dict[str, TextChunk],
    ) -> dict[str, list[RiskFinding]]:
        findings_by_category: dict[str, list[RiskFinding]] = {}
        agent_by_label = {agent.category_label: agent for agent in self.domain_agents}

        for agent in self.domain_agents:
            findings_by_category[agent.category_label] = agent.analyze(triage_results, chunks_by_id)

        for source_category, target_categories in CATEGORY_PROPAGATION_MAP.items():
            source_findings = findings_by_category.get(source_category, [])
            if not source_findings:
                continue
            for target_category in target_categories:
                target_agent = agent_by_label.get(target_category)
                if target_agent is None:
                    continue
                extra_triage, extra_chunk = self._build_propagation_context(
                    source_category=source_category,
                    target_category=target_category,
                    source_findings=source_findings,
                )
                if extra_triage is None or extra_chunk is None:
                    continue
                local_chunks = dict(chunks_by_id)
                local_chunks[extra_chunk.chunk_id] = extra_chunk
                propagated = target_agent.analyze([extra_triage], local_chunks)
                if not propagated:
                    continue
                existing = findings_by_category.setdefault(target_category, [])
                existing_ids = {finding.finding_id for finding in existing}
                for finding in propagated:
                    finding.related_category_hint = sorted(set(finding.related_category_hint + [source_category]))
                    if "cross_agent_propagation" not in finding.trigger_signal_matched:
                        finding.trigger_signal_matched.append("cross_agent_propagation")
                    if finding.finding_id not in existing_ids:
                        existing.append(finding)
        return findings_by_category

    def _build_propagation_context(
        self,
        source_category: str,
        target_category: str,
        source_findings: list[RiskFinding],
    ) -> tuple[TriageResult | None, TextChunk | None]:
        evidence_parts = [finding.evidence for finding in source_findings[:3] if finding.evidence]
        if not evidence_parts:
            return None, None
        synthetic_chunk_id = f"propagation-{source_category}-{target_category}"
        synthetic_text = (
            f"来自{source_category}的关联证据："
            + "；".join(evidence_parts)
            + f"。请从{target_category}视角复核这些事实是否会产生传导风险。"
        )
        return (
            TriageResult(
                chunk_id=synthetic_chunk_id,
                text=synthetic_text,
                candidate_risk_types=[target_category],
                relevance_score=max(finding.confidence for finding in source_findings),
                rationale=f"{source_category} 命中后触发对 {target_category} 的一次传导复核。",
            ),
            TextChunk(
                chunk_id=synthetic_chunk_id,
                text=synthetic_text,
                source_type="propagated_context",
                source_name=f"{source_category}->{target_category}",
            ),
        )

    def run(self, analysis_input: AnalysisInput) -> dict:
        state = self.run_state(analysis_input)
        return self._build_output(state)

    def _resolve_final_findings(self, state: PipelineState) -> list[RiskFinding]:
        if state.verification_result is None:
            return flatten_findings(state.domain_findings)
        if state.verification_result.verdict == "revert_to_original":
            return flatten_findings(state.domain_findings)
        return flatten_findings(state.revised_findings)

    def _normalize_input(self, analysis_input: AnalysisInput) -> AnalysisInput:
        if analysis_input.input_type == "document":
            return analysis_input
        if analysis_input.input_type == "company_name":
            if not analysis_input.company_name:
                raise ValueError("company_name input requires company_name.")
            return self.company_data_collector.collect(
                analysis_input.company_name,
                analysis_input.metadata,
            )
        raise ValueError(f"Unsupported input_type: {analysis_input.input_type}")

    def _build_output(self, state: PipelineState) -> dict:
        if state.risk_report is None:
            raise ValueError("Risk report has not been built.")
        return {
            "report": state.risk_report.model_dump(),
            "debug": {
                "workflow_backend": self.workflow_backend,
                "input_type": state.analysis_input.input_type,
                "chunk_count": len(state.chunks),
                "triage_count": len(state.triage_results),
                "needs_human_review": state.needs_human_review,
                "triage_results": [result.model_dump() for result in state.triage_results],
                "reflection_result": state.reflection_result.model_dump() if state.reflection_result else None,
                "confidence_result": state.confidence_result.model_dump() if state.confidence_result else None,
                "verification_result": state.verification_result.model_dump() if state.verification_result else None,
                "final_findings": [finding.model_dump() for finding in state.final_findings],
                "pipeline_state": state.model_dump(),
            },
        }

    def _build_report(self, state: PipelineState):
        company = state.analysis_input.company_name or "未知企业"
        previous_report = self.history_store.get_latest_report(company)
        suggestions = self.recommendation_store.suggest_for_findings(state.final_findings)
        base_report = build_risk_report(
            company=company,
            timestamp=state.timestamp,
            findings=state.final_findings,
            suggestions=suggestions,
            confidence_result=state.confidence_result,
            trend=None,
            trend_delta=None,
            force_human_review=state.needs_human_review,
        )
        trend, trend_delta = compute_trend(base_report.overall_score, previous_report)
        return build_risk_report(
            company=company,
            timestamp=state.timestamp,
            findings=state.final_findings,
            suggestions=suggestions,
            confidence_result=state.confidence_result,
            trend=trend,
            trend_delta=trend_delta,
            force_human_review=state.needs_human_review,
        )
