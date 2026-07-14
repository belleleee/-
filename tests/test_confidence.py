from unittest import TestCase

from risk_himate.app.core.confidence import ConfidenceEvaluator
from risk_himate.app.core.schemas import AnalysisInput, PipelineState, ReflectionIssue, ReflectionResult, RiskFinding


class ConfidenceEvaluatorTests(TestCase):
    def test_confidence_evaluator_returns_continuous_score_and_gate_flags(self) -> None:
        finding = RiskFinding(
            finding_id="data-1",
            category="数据合规风险",
            subtype="数据共享与出境",
            exists=True,
            severity="high",
            confidence=0.9,
            evidence="本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。",
            evidence_chunk_ids=["chunk-001"],
            rationale="涉及敏感个人信息、境外存储和告知不足。",
            legal_basis=["《个人信息保护法》"],
            trigger_signal_matched=["面部识别", "境外服务器", "未向用户明确告知"],
            lifecycle_stage_hint="商业出海",
        )
        state = PipelineState(
            analysis_input=AnalysisInput(input_type="document", company_name="测试企业", raw_text="测试"),
            timestamp="2026-07-14T00:00:00+00:00",
            revised_findings={"数据合规风险": [finding]},
        )

        result = ConfidenceEvaluator().evaluate(state)

        self.assertGreater(result.confidence_score, 0.7)
        self.assertTrue(result.gate_flags.privacy_legality_redline)
        self.assertFalse(result.gate_flags.ethics_fairness_redline)

    def test_confidence_evaluator_penalizes_cross_agent_disagreement(self) -> None:
        finding = RiskFinding(
            finding_id="algo-1",
            category="算法安全风险",
            subtype="算法操纵诱导",
            exists=True,
            severity="high",
            confidence=0.8,
            evidence="系统通过个性化策略持续诱导用户高频交易。",
            evidence_chunk_ids=["chunk-001"],
            rationale="存在明显诱导。",
            legal_basis=["《互联网信息服务算法推荐管理规定》"],
            trigger_signal_matched=["诱导"],
            cross_agent_disagreement=True,
        )
        state = PipelineState(
            analysis_input=AnalysisInput(input_type="document", company_name="测试企业", raw_text="测试"),
            timestamp="2026-07-14T00:00:00+00:00",
            revised_findings={"算法安全风险": [finding]},
            reflection_result=ReflectionResult(
                issues=[
                    ReflectionIssue(
                        issue_id="issue-1",
                        issue_type="severity_issue",
                        category="算法安全风险",
                        related_finding_id="algo-1",
                        description="Finding algo-1 与 ethics-1 对同一事实存在跨agent分歧，当前按较高严重度处理。",
                        suggested_fix="提高人工复核优先级。",
                        confidence=0.7,
                    )
                ],
                overall_confidence=0.7,
                summary="存在跨agent分歧。",
            ),
        )

        result = ConfidenceEvaluator().evaluate(state)

        self.assertLess(result.cross_agent_consistency, 0.8)
        self.assertTrue(result.disagreement_flags)
