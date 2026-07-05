"""Report-building utilities for Step 3."""

from __future__ import annotations

from risk_himate.app.core.analysis import (
    average_confidence,
    compute_finding_score,
    compute_overall_score,
    score_to_level,
    top_categories,
)
from risk_himate.app.core.schemas import RiskFinding, RiskReport, RiskReportDetail


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
        needs_human_review=needs_human_review,
        revision_reason=finding.revision_reason,
    )


def build_risk_report(
    company: str,
    timestamp: str,
    findings: list[RiskFinding],
    suggestions: dict[str, str],
    trend: str | None,
    trend_delta: float | None,
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

    return RiskReport(
        company=company,
        timestamp=timestamp,
        overall_risk_level=score_to_level(overall_score),
        overall_score=overall_score,
        confidence=average_confidence(findings),
        risk_details=details,
        top3_risks=top_risks,
        human_review_items=human_review_items,
        trend=trend,
        trend_delta=trend_delta,
        top_categories=top_categories(findings),
    )
