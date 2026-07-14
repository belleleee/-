from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from risk_himate.app.main import main
from risk_himate.app.core.schemas import AnalysisInput, PipelineState
from risk_himate.app.core.schemas import RiskReport


class CLITests(TestCase):
    def _make_fake_state(self, report: dict) -> PipelineState:
        return PipelineState(
            analysis_input=AnalysisInput(
                input_type="document",
                company_name=report["company"],
                raw_text="测试文本",
                metadata={},
            ),
            timestamp=report["timestamp"],
            needs_human_review=False,
            risk_report=RiskReport(**report),
        )

    def test_cli_writes_full_result_to_output_file(self) -> None:
        fake_report = {
            "company": "测试企业",
            "timestamp": "2026-07-06T00:00:00+00:00",
            "overall_risk_level": "medium",
            "overall_score": 42.0,
            "confidence": 0.8,
            "risk_details": [],
            "top3_risks": [],
            "human_review_items": [],
            "trend": None,
            "trend_delta": None,
            "top_categories": [],
        }

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            stdout_buffer = io.StringIO()
            argv = [
                "risk_himate.app.main",
                "--input-type",
                "document",
                "--company",
                "测试企业",
                "--text",
                "测试文本",
                "--output",
                str(output_path),
            ]
            with patch.object(sys, "argv", argv), patch(
                "risk_himate.app.main.RiskHiMATEPipeline.run_state",
                return_value=self._make_fake_state(fake_report),
            ), patch("sys.stdout", stdout_buffer):
                main()

            written = json.loads(output_path.read_text(encoding="utf-8"))
            printed = json.loads(stdout_buffer.getvalue())
            self.assertIn("report", written)
            self.assertIn("debug", written)
            self.assertEqual(written, printed)

    def test_cli_report_only_writes_report_payload(self) -> None:
        fake_report = {
            "company": "测试企业",
            "timestamp": "2026-07-06T00:00:00+00:00",
            "overall_risk_level": "low",
            "overall_score": 20.0,
            "confidence": 0.9,
            "risk_details": [],
            "top3_risks": [],
            "human_review_items": [],
            "trend": None,
            "trend_delta": None,
            "top_categories": [],
        }

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report_only.json"
            stdout_buffer = io.StringIO()
            argv = [
                "risk_himate.app.main",
                "--input-type",
                "document",
                "--company",
                "测试企业",
                "--text",
                "测试文本",
                "--output",
                str(output_path),
                "--report-only",
            ]
            with patch.object(sys, "argv", argv), patch(
                "risk_himate.app.main.RiskHiMATEPipeline.run_state",
                return_value=self._make_fake_state(fake_report),
            ), patch("sys.stdout", stdout_buffer):
                main()

            written = json.loads(output_path.read_text(encoding="utf-8"))
            printed = json.loads(stdout_buffer.getvalue())
            self.assertNotIn("debug", written)
            self.assertEqual(written["company"], "测试企业")
            self.assertEqual(written, printed)

    def test_cli_can_write_markdown_rendered_report(self) -> None:
        fake_report = {
            "company": "测试企业",
            "timestamp": "2026-07-06T00:00:00+00:00",
            "overall_risk_level": "medium",
            "overall_score": 55.0,
            "confidence": 0.88,
            "risk_details": [],
            "top3_risks": [],
            "human_review_items": [],
            "trend": None,
            "trend_delta": None,
            "top_categories": [],
        }

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            rendered_path = Path(tmpdir) / "report.md"
            stdout_buffer = io.StringIO()
            argv = [
                "risk_himate.app.main",
                "--input-type",
                "document",
                "--company",
                "测试企业",
                "--text",
                "测试文本",
                "--output",
                str(output_path),
                "--report-only",
                "--rendered-report",
                str(rendered_path),
            ]
            with patch.object(sys, "argv", argv), patch(
                "risk_himate.app.main.RiskHiMATEPipeline.run_state",
                return_value=self._make_fake_state(fake_report),
            ), patch("sys.stdout", stdout_buffer):
                main()

            rendered = rendered_path.read_text(encoding="utf-8")
            self.assertIn("风险分析报告", rendered)
            self.assertIn("执行摘要", rendered)
