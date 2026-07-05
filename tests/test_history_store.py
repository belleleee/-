from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from risk_himate.app.core.schemas import RiskReport
from risk_himate.app.storage.history_store import JsonHistoryStore, SQLiteHistoryStore


class HistoryStoreTests(TestCase):
    def test_json_history_store_round_trip(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "history.json"
            store = JsonHistoryStore(str(path))
            report = RiskReport(
                company="示例科技",
                timestamp="2026-07-05T00:00:00+00:00",
                overall_risk_level="medium",
                overall_score=55.0,
                confidence=0.8,
                risk_details=[],
                top3_risks=[],
                human_review_items=[],
                trend=None,
                trend_delta=None,
                top_categories=[],
            )
            store.save_report(report)
            loaded = store.get_latest_report("示例科技")

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.company, "示例科技")
            self.assertEqual(loaded.overall_score, 55.0)

    def test_sqlite_history_store_round_trip(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "history.db"
            store = SQLiteHistoryStore(str(path))
            report = RiskReport(
                company="示例科技",
                timestamp="2026-07-06T00:00:00+00:00",
                overall_risk_level="high",
                overall_score=82.0,
                confidence=0.86,
                risk_details=[],
                top3_risks=[],
                human_review_items=[],
                trend=None,
                trend_delta=None,
                top_categories=[],
            )
            store.save_report(report)
            loaded = store.get_latest_report("示例科技")

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.overall_risk_level, "high")
            self.assertEqual(loaded.overall_score, 82.0)
