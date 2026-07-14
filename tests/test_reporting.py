from unittest import TestCase

from risk_himate.app.core.presentation import render_risk_report_markdown
from risk_himate.app.core.presentation import render_risk_report_rtf
from risk_himate.app.core.reporting import build_risk_report
from risk_himate.app.core.schemas import RiskFinding


class ReportingTests(TestCase):
    def test_build_risk_report_marks_low_confidence_for_human_review(self) -> None:
        finding = RiskFinding(
            finding_id="f-1",
            category="数据合规风险",
            subtype="数据共享与出境",
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
        self.assertTrue(report.lifecycle_stage_groups)
        self.assertEqual(report.lifecycle_stage_groups[0].stage, "商业出海")

    def test_render_risk_report_markdown_includes_analysis_and_solution(self) -> None:
        finding = RiskFinding(
            finding_id="f-1",
            category="数据合规风险",
            subtype="数据共享与出境",
            exists=True,
            severity="high",
            confidence=0.81,
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

        markdown = render_risk_report_markdown(report)

        self.assertIn("执行摘要", markdown)
        self.assertIn("按生命周期阶段的风险分析与解决方案", markdown)
        self.assertIn("风险分析：", markdown)
        self.assertIn("解决方案：建议立即开展数据出境合规评估。", markdown)

    def test_render_risk_report_rtf_has_rtf_header(self) -> None:
        finding = RiskFinding(
            finding_id="f-1",
            category="数据合规风险",
            subtype="数据共享与出境",
            exists=True,
            severity="high",
            confidence=0.81,
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

        rtf = render_risk_report_rtf(report)

        self.assertTrue(rtf.startswith("{\\rtf1"))
        self.assertIn("风险分析报告", rtf)
