from unittest import TestCase

from risk_himate.app.agents.reflection_agent import ReflectionAgent
from risk_himate.app.core.schemas import AnalysisInput
from risk_himate.app.core.schemas import RiskFinding
from risk_himate.app.workflows.pipeline import RiskHiMATEPipeline


class ReflectionCycleTests(TestCase):
    def test_reflection_keeps_high_severity_for_sensitive_cross_border_data_case(self) -> None:
        finding = RiskFinding(
            finding_id="data_compliance-chunk-000",
            category="数据合规风险",
            subtype="数据采集合规",
            exists=True,
            severity="high",
            confidence=0.9,
            evidence="本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。",
            evidence_chunk_ids=["chunk-000"],
            rationale="涉及敏感个人信息、境外存储和未明确告知。",
            legal_basis=["《个人信息保护法》", "《数据安全法》"],
        )

        issues = ReflectionAgent()._find_severity_issues([finding])

        self.assertFalse(
            any(issue.related_finding_id == finding.finding_id for issue in issues),
            "Expected reflection not to downgrade a clearly high-risk data compliance finding.",
        )

    def test_reflection_revision_verification_chain_updates_subtype(self) -> None:
        text = "企业计划将用户个人信息和行为数据传输到境外云平台，以支持海外客户的推荐服务。"
        pipeline = RiskHiMATEPipeline()
        state = pipeline.run_state(
            AnalysisInput(
                input_type="document",
                company_name="跨境样例科技",
                raw_text=text,
            )
        )

        self.assertIsNotNone(state.reflection_result)
        self.assertTrue(
            any(issue.issue_type == "misclassified" for issue in state.reflection_result.issues),
            "Expected reflection to detect a subtype issue for cross-border transfer.",
        )
        data_findings = state.revised_findings.get("数据合规风险", [])
        self.assertTrue(data_findings, "Expected revised data compliance findings.")
        self.assertEqual(data_findings[0].subtype, "跨境数据传输")
        self.assertIsNotNone(state.verification_result)
        self.assertIn(state.verification_result.verdict, {"accept", "partial_accept"})
