"""Report-building utilities for Step 3."""

from __future__ import annotations

from collections import defaultdict

from risk_himate.app.core.analysis import (
    average_confidence,
    compute_finding_score,
    compute_overall_score,
    resolve_lifecycle_stage,
    score_to_level,
    top_categories,
)
from risk_himate.app.core.schemas import ConfidenceResult, GateFlags
from risk_himate.app.core.schemas import LifecycleStageGroup, RiskFinding, RiskReport, RiskReportDetail
from risk_himate.app.core.taxonomy import CATEGORY_PROPAGATION_MAP, LIFECYCLE_STAGES


def build_report_detail(
    finding: RiskFinding,
    suggestion: str,
    needs_human_review: bool,
) -> RiskReportDetail:
    return RiskReportDetail(
        finding_id=finding.finding_id,
        category=finding.category,
        subtype=finding.subtype,
        severity=finding.severity,
        score=compute_finding_score(finding),
        confidence=round(finding.confidence, 2),
        evidence=finding.evidence,
        suggestion=suggestion,
        legal_basis=finding.legal_basis,
        trigger_signal_matched=finding.trigger_signal_matched,
        related_category_hint=finding.related_category_hint,
        lifecycle_stage_hint=resolve_lifecycle_stage(finding),
        cross_agent_disagreement=finding.cross_agent_disagreement,
        needs_human_review=needs_human_review,
        revision_reason=finding.revision_reason,
    )


def build_lifecycle_stage_groups(details: list[RiskReportDetail]) -> list[LifecycleStageGroup]:
    grouped: dict[str, list[RiskReportDetail]] = defaultdict(list)
    for detail in details:
        grouped[detail.lifecycle_stage_hint or "场景落地"].append(detail)

    stage_groups: list[LifecycleStageGroup] = []
    for stage in LIFECYCLE_STAGES:
        stage_details = sorted(
            grouped.get(stage, []),
            key=lambda detail: (-detail.score, -detail.confidence, detail.category),
        )
        if not stage_details:
            continue
        stage_groups.append(
            LifecycleStageGroup(
                stage=stage,
                summary=_stage_summary(stage, stage_details),
                risk_details=stage_details,
                propagation_hints=_stage_propagation_hints(stage_details),
            )
        )
    return stage_groups


def _stage_summary(stage: str, details: list[RiskReportDetail]) -> str:
    highest = details[0]
    return (
        f"{stage}阶段共识别 {len(details)} 条风险，"
        f"当前最突出的风险是“{highest.category} / {highest.subtype}”。"
    )


def _stage_propagation_hints(details: list[RiskReportDetail]) -> list[str]:
    hints: list[str] = []
    seen: set[str] = set()
    for detail in details:
        source_targets = CATEGORY_PROPAGATION_MAP.get(detail.category, [])
        for target in source_targets:
            message = (
                f"传导提示：{detail.category}中的“{detail.subtype}”可能继续传导至{target}，"
                "建议联动复核相关制度与证据。"
            )
            if message not in seen:
                seen.add(message)
                hints.append(message)
        for related in detail.related_category_hint:
            message = (
                f"关联提示：{detail.category}中的“{detail.subtype}”与{related}存在潜在联动，"
                "建议在后续复核中一并检查。"
            )
            if message not in seen:
                seen.add(message)
                hints.append(message)
    return hints


def build_risk_report(
    company: str,
    timestamp: str,
    findings: list[RiskFinding],
    suggestions: dict[str, str],
    trend: str | None,
    trend_delta: float | None,
    confidence_result: ConfidenceResult | None = None,
    force_human_review: bool = False,
) -> RiskReport:
    details = [
        build_report_detail(
            finding,
            suggestion=suggestions.get(finding.finding_id, ""),
            needs_human_review=force_human_review or finding.confidence < 0.6,
        )
        for finding in findings
    ]
    details = sorted(details, key=lambda detail: (-detail.score, -detail.confidence, detail.category))
    overall_score = compute_overall_score(findings)
    top_risks = details[:3]
    human_review_items = [detail for detail in details if detail.needs_human_review]
    stage_groups = build_lifecycle_stage_groups(details)
    propagation_hints = [hint for group in stage_groups for hint in group.propagation_hints]

    return RiskReport(
        company=company,
        timestamp=timestamp,
        overall_risk_level=score_to_level(overall_score),
        overall_score=overall_score,
        confidence=confidence_result.confidence_score if confidence_result else average_confidence(findings),
        confidence_breakdown=confidence_result,
        risk_details=details,
        top3_risks=top_risks,
        human_review_items=human_review_items,
        lifecycle_stage_groups=stage_groups,
        propagation_hints=propagation_hints,
        gate_flags=confidence_result.gate_flags if confidence_result else GateFlags(),
        trend=trend,
        trend_delta=trend_delta,
        top_categories=top_categories(findings),
    )
