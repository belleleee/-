from unittest import TestCase

from risk_himate.app.core.reporting import build_risk_report
from risk_himate.app.core.schemas import RiskFinding


class ReportingTests(TestCase):
    def test_build_risk_report_marks_low_confidence_for_human_review(self) -> None:
        finding = RiskFinding(
            finding_id="f-1",
            category="数据合规风险",
            subtype="跨境数据传输",
            exists=True,
            severity="high",
            confidence=0.45,
            evidence="用户数据被传输到境外云平台。",
            evidence_chunk_ids=["chunk-001"],
            rationale="sample",
            legal_basis=["《个人信息保护法》"],
        )

        report = build_risk_report(
            company="测试企业",
            timestamp="2026-07-05T00:00:00+00:00",
            findings=[finding],
            suggestions={"f-1": "建议立即开展数据出境合规评估。"},
            trend=None,
            trend_delta=None,
        )

        self.assertEqual(report.top3_risks[0].finding_id, "f-1")
        self.assertTrue(report.human_review_items)
        self.assertTrue(report.risk_details[0].needs_human_review)
