from unittest import TestCase

from risk_himate.app.agents.triage_agent import TriageAgent
from risk_himate.app.core.schemas import TextChunk


class TriageTests(TestCase):
    def test_triage_returns_schema_shape(self) -> None:
        chunks = [
            TextChunk(
                chunk_id="chunk-001",
                text="企业计划将用户个人信息传输到境外云平台，并用于算法推荐优化。",
                source_type="document",
            )
        ]

        results = TriageAgent().analyze(chunks)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, "chunk-001")
        self.assertIn("数据合规风险", results[0].candidate_risk_types)
        self.assertGreater(results[0].relevance_score, 0)
