"""Pipeline orchestration for Step 1 and Step 2."""

from __future__ import annotations

from datetime import datetime, UTC

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
from risk_himate.app.core.reporting import build_risk_report
from risk_himate.app.core.schemas import AnalysisInput, PipelineState, RiskFinding
from risk_himate.app.llm.client import OpenAICompatibleLLMClient
from risk_himate.app.rag.recommendation_store import LocalRecommendationStore, RecommendationStore
from risk_himate.app.storage.history_store import HistoryStore, NullHistoryStore, compute_trend


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
        self.verifier_agent = VerifierAgent(llm_client=llm_client)
        self.recommendation_store = recommendation_store or LocalRecommendationStore()
        self.history_store = history_store or NullHistoryStore()
        self.company_data_collector = company_data_collector or ExternalCompanyDataCollector.from_env(
            fallback_collector=LocalCompanyDataCollector()
        )

    def run_state(self, analysis_input: AnalysisInput) -> PipelineState:
        analysis_input = self._normalize_input(analysis_input)
        if not analysis_input.raw_text:
            raise ValueError("Analysis input must include raw_text after normalization.")

        timestamp = datetime.now(UTC).isoformat()
        chunks = chunk_text(analysis_input.raw_text)
        chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        triage_results = self.triage_agent.analyze(chunks)
        #准备数据

        findings_by_category: dict[str, list[RiskFinding]] = {}
        for agent in self.domain_agents:
            findings_by_category[agent.category_label] = agent.analyze(triage_results, chunks_by_id)
            #五个agent并行分析

        state = PipelineState(
            analysis_input=analysis_input,
            timestamp=timestamp,
            chunks=chunks,
            triage_results=triage_results,
            domain_findings=findings_by_category,
        )
        #存储状态
        state.reflection_result = self.reflection_agent.analyze(state)
        state.revised_findings = self.revision_agent.revise(state)
        state.verification_result = self.verifier_agent.verify(state)
        state.final_findings = self._resolve_final_findings(state)
        state.needs_human_review = state.verification_result.needs_human_review
        #完成四阶段验证循环
        state.risk_report = self._build_report(state)
        self.history_store.save_report(state.risk_report)
        return state

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
                "input_type": state.analysis_input.input_type,
                "chunk_count": len(state.chunks),
                "triage_count": len(state.triage_results),
                "needs_human_review": state.needs_human_review,
                "triage_results": [result.model_dump() for result in state.triage_results],
                "reflection_result": state.reflection_result.model_dump() if state.reflection_result else None,
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
            trend=trend,
            trend_delta=trend_delta,
            force_human_review=state.needs_human_review,
        )
