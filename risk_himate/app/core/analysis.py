"""Helpers for finding aggregation and lightweight scoring."""

from __future__ import annotations

from risk_himate.app.core.schemas import RiskFinding
from risk_himate.app.core.taxonomy import RISK_TAXONOMY, RISK_LABEL_TO_CODE


SEVERITY_SCORES = {
    "low": 30,
    "medium": 60,
    "high": 90,
}


def flatten_findings(findings_by_category: dict[str, list[RiskFinding]]) -> list[RiskFinding]:
    flattened: list[RiskFinding] = []
    for findings in findings_by_category.values():
        flattened.extend(findings)
    return flattened


def average_confidence(findings: list[RiskFinding]) -> float:
    if not findings:
        return 0.0
    return round(sum(finding.confidence for finding in findings) / len(findings), 2)


def compute_finding_score(finding: RiskFinding) -> float:
    category_code = RISK_LABEL_TO_CODE.get(finding.category)
    weight = 1.0
    if category_code and category_code in RISK_TAXONOMY:
        weight = float(RISK_TAXONOMY[category_code]["weight"])
    severity_score = SEVERITY_SCORES.get(finding.severity, 0)
    adjusted = severity_score * weight * (0.7 + 0.3 * finding.confidence)
    return round(min(100.0, adjusted), 2)


def compute_overall_score(findings: list[RiskFinding]) -> float:
    if not findings:
        return 0.0
    total = sum(compute_finding_score(finding) for finding in findings)
    return round(min(100.0, total / max(len(findings), 1)), 2)


def score_to_level(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def top_categories(findings: list[RiskFinding]) -> list[str]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.category] = counts.get(finding.category, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [category for category, _ in ranked[:3]]
