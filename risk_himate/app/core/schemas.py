"""Shared schemas for Risk-HiMATE pipeline."""

from __future__ import annotations

from typing import Literal

from .compat import BaseModel, Field


class AnalysisInput(BaseModel):
    input_type: Literal["document", "company_name"]
    company_name: str | None = None
    raw_text: str | None = None
    metadata: dict = Field(default_factory=dict)


class TextChunk(BaseModel):
    chunk_id: str
    text: str
    source_type: str
    source_name: str | None = None
    page: int | None = None
    paragraph_index: int | None = None


class TriageResult(BaseModel):
    chunk_id: str
    text: str
    candidate_risk_types: list[str]
    relevance_score: float
    rationale: str


class RiskFinding(BaseModel):
    finding_id: str
    category: str
    subtype: str
    exists: bool
    severity: Literal["low", "medium", "high"]
    confidence: float
    evidence: str
    evidence_chunk_ids: list[str]
    rationale: str
    legal_basis: list[str] = Field(default_factory=list)
    trigger_signal_matched: list[str] = Field(default_factory=list)
    related_category_hint: list[str] = Field(default_factory=list)
    lifecycle_stage_hint: str | None = None
    cross_agent_disagreement: bool = False
    revision_reason: str | None = None


class RiskReportDetail(BaseModel):
    finding_id: str
    category: str
    subtype: str
    severity: Literal["low", "medium", "high"]
    score: float
    confidence: float
    evidence: str
    suggestion: str
    legal_basis: list[str] = Field(default_factory=list)
    trigger_signal_matched: list[str] = Field(default_factory=list)
    related_category_hint: list[str] = Field(default_factory=list)
    lifecycle_stage_hint: str | None = None
    cross_agent_disagreement: bool = False
    needs_human_review: bool = False
    revision_reason: str | None = None


class LifecycleStageGroup(BaseModel):
    stage: str
    summary: str
    risk_details: list[RiskReportDetail] = Field(default_factory=list)
    propagation_hints: list[str] = Field(default_factory=list)


class ReflectionIssue(BaseModel):
    issue_id: str
    issue_type: Literal["missing_risk", "misclassified", "severity_issue"]
    category: str | None = None
    chunk_id: str | None = None
    related_finding_id: str | None = None
    description: str
    suggested_fix: str
    suggested_category: str | None = None
    suggested_subtype: str | None = None
    suggested_severity: Literal["low", "medium", "high"] | None = None
    confidence: float


class ReflectionResult(BaseModel):
    issues: list[ReflectionIssue]
    overall_confidence: float
    summary: str


class GateFlags(BaseModel):
    privacy_legality_redline: bool = False
    ethics_fairness_redline: bool = False
    triggered_reasons: list[str] = Field(default_factory=list)


class ConfidenceResult(BaseModel):
    confidence_score: float
    signal_strength: float
    robustness: float
    cross_agent_consistency: float
    disagreement_flags: list[str] = Field(default_factory=list)
    gate_flags: GateFlags = Field(default_factory=GateFlags)
    summary: str = ""


class VerificationResult(BaseModel):
    verdict: Literal["accept", "partial_accept", "revert_to_original"]
    confidence: float
    accepted_finding_ids: list[str]
    rejected_finding_ids: list[str]
    needs_human_review: bool
    notes: str


class RiskReport(BaseModel):
    company: str
    timestamp: str
    overall_risk_level: Literal["low", "medium", "high"]
    overall_score: float
    confidence: float
    confidence_breakdown: ConfidenceResult | None = None
    risk_details: list[RiskReportDetail]
    top3_risks: list[RiskReportDetail]
    human_review_items: list[RiskReportDetail] = Field(default_factory=list)
    lifecycle_stage_groups: list[LifecycleStageGroup] = Field(default_factory=list)
    propagation_hints: list[str] = Field(default_factory=list)
    gate_flags: GateFlags = Field(default_factory=GateFlags)
    trend: str | None = None
    trend_delta: float | None = None
    top_categories: list[str] = Field(default_factory=list)


class PipelineState(BaseModel):
    analysis_input: AnalysisInput
    timestamp: str
    chunks: list[TextChunk] = Field(default_factory=list)
    triage_results: list[TriageResult] = Field(default_factory=list)
    domain_findings: dict[str, list[RiskFinding]] = Field(default_factory=dict)
    reflection_result: ReflectionResult | None = None
    revised_findings: dict[str, list[RiskFinding]] = Field(default_factory=dict)
    confidence_result: ConfidenceResult | None = None
    verification_result: VerificationResult | None = None
    final_findings: list[RiskFinding] = Field(default_factory=list)
    needs_human_review: bool = False
    risk_report: RiskReport | None = None
