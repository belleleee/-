from unittest import TestCase

from risk_himate.app.core.schemas import AnalysisInput, RiskReport
from risk_himate.app.storage.history_store import JsonHistoryStore
from risk_himate.app.storage.history_store import HistoryStore
from risk_himate.app.workflows.pipeline import RiskHiMATEPipeline
from tempfile import TemporaryDirectory
from pathlib import Path


class InMemoryHistoryStore(HistoryStore):
    def __init__(self, previous_report: RiskReport | None = None) -> None:
        self.previous_report = previous_report
        self.saved_reports: list[RiskReport] = []

    def get_latest_report(self, company: str) -> RiskReport | None:
        return self.previous_report

    def save_report(self, report: RiskReport) -> None:
        self.saved_reports.append(report)


class PipelineTests(TestCase):
    def test_pipeline_runs_end_to_end(self) -> None:
        text = (
            "公司通过智能推荐系统向海外客户提供服务，部分用户行为数据将存储在境外云平台。"
            "同时，公司核心算法暂未披露可解释性机制，且存在专利侵权争议。"
        )
        pipeline = RiskHiMATEPipeline()
        result = pipeline.run(
            AnalysisInput(
                input_type="document",
                company_name="示例科技",
                raw_text=text,
            )
        )

        report = result["report"]
        self.assertEqual(report["company"], "示例科技")
        self.assertGreaterEqual(result["debug"]["chunk_count"], 1)
        self.assertIn("risk_details", report)
        self.assertIn("confidence_result", result["debug"])
        self.assertIn("confidence_breakdown", report)
        self.assertTrue(
            report["risk_details"],
            "Expected at least one risk finding in the sample text.",
        )

    def test_pipeline_builds_trend_and_suggestions(self) -> None:
        previous_report = RiskReport(
            company="示例科技",
            timestamp="2026-07-01T00:00:00+00:00",
            overall_risk_level="low",
            overall_score=20.0,
            confidence=0.7,
            risk_details=[],
            top3_risks=[],
            human_review_items=[],
            trend=None,
            trend_delta=None,
            top_categories=[],
        )
        history_store = InMemoryHistoryStore(previous_report=previous_report)
        pipeline = RiskHiMATEPipeline(history_store=history_store)
        result = pipeline.run(
            AnalysisInput(
                input_type="document",
                company_name="示例科技",
                raw_text="企业计划将用户个人信息传输到境外云平台，并面向海外客户提供服务。",
            )
        )

        report = result["report"]
        self.assertEqual(report["trend"], "up")
        self.assertIsInstance(report["trend_delta"], float)
        self.assertTrue(report["top3_risks"])
        self.assertTrue(report["risk_details"][0]["suggestion"])
        self.assertEqual(len(history_store.saved_reports), 1)

    def test_pipeline_supports_company_name_input(self) -> None:
        pipeline = RiskHiMATEPipeline()
        result = pipeline.run(
            AnalysisInput(
                input_type="company_name",
                company_name="示例科技",
            )
        )

        report = result["report"]
        self.assertEqual(report["company"], "示例科技")
        self.assertTrue(report["risk_details"])
        self.assertGreaterEqual(result["debug"]["chunk_count"], 1)

    def test_pipeline_can_use_persistent_json_history_store(self) -> None:
        with TemporaryDirectory() as tmpdir:
            history_path = Path(tmpdir) / "history.json"
            store = JsonHistoryStore(str(history_path))
            pipeline = RiskHiMATEPipeline(history_store=store)

            first = pipeline.run(
                AnalysisInput(
                    input_type="company_name",
                    company_name="跨境样例科技",
                )
            )
            second = pipeline.run(
                AnalysisInput(
                    input_type="company_name",
                    company_name="跨境样例科技",
                    metadata={"risk_signals": ["新增专利侵权争议", "面向更多海外市场扩张"]},
                )
            )

            self.assertIsNone(first["report"]["trend"])
            self.assertIn(second["report"]["trend"], {"up", "stable", "down"})
