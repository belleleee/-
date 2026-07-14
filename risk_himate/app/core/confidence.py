"""Independent confidence evaluation for Risk-HiMATE."""

from __future__ import annotations

from risk_himate.app.core.analysis import flatten_findings
from risk_himate.app.core.schemas import ConfidenceResult, GateFlags, PipelineState, RiskFinding


class ConfidenceEvaluator:
    """Scores finding stability separately from verifier verdict gating."""

    def evaluate(self, state: PipelineState) -> ConfidenceResult:
        findings = flatten_findings(state.revised_findings) or flatten_findings(state.domain_findings)
        disagreement_flags = self._collect_disagreement_flags(state, findings)
        signal_strength = self._signal_strength(findings)
        robustness = self._robustness(state, findings)
        consistency = self._cross_agent_consistency(state, findings, disagreement_flags)
        gate_flags = self._gate_flags(findings)
        confidence_score = round(
            min(1.0, max(0.0, 0.4 * signal_strength + 0.3 * robustness + 0.3 * consistency)),
            2,
        )
        summary = (
            f"signal_strength={signal_strength:.2f}, robustness={robustness:.2f}, "
            f"cross_agent_consistency={consistency:.2f}"
        )
        return ConfidenceResult(
            confidence_score=confidence_score,
            signal_strength=signal_strength,
            robustness=robustness,
            cross_agent_consistency=consistency,
            disagreement_flags=disagreement_flags,
            gate_flags=gate_flags,
            summary=summary,
        )

    def _signal_strength(self, findings: list[RiskFinding]) -> float:
        if not findings:
            return 0.0
        scores: list[float] = []
        for finding in findings:
            signal_count = len([token for token in finding.trigger_signal_matched if token])
            direct_evidence_bonus = 0.1 if len(finding.evidence.strip()) >= 20 else 0.0
            severity_bonus = {"low": 0.0, "medium": 0.08, "high": 0.15}.get(finding.severity, 0.0)
            score = min(1.0, 0.35 + 0.12 * signal_count + direct_evidence_bonus + severity_bonus)
            scores.append(score)
        return round(sum(scores) / len(scores), 2)

    def _robustness(self, state: PipelineState, findings: list[RiskFinding]) -> float:
        if not findings:
            return 0.0
        completeness_scores: list[float] = []
        for finding in findings:
            score = 0.25
            if finding.evidence_chunk_ids:
                score += 0.2
            if finding.legal_basis:
                score += 0.15
            if len(finding.evidence.strip()) >= 30:
                score += 0.2
            if len(finding.rationale.strip()) >= 12:
                score += 0.1
            if finding.lifecycle_stage_hint:
                score += 0.1
            completeness_scores.append(min(1.0, score))

        issue_penalty = 0.0
        if state.reflection_result and findings:
            issue_penalty = min(0.35, 0.08 * len(state.reflection_result.issues) / len(findings))
        return round(max(0.0, min(1.0, sum(completeness_scores) / len(completeness_scores) - issue_penalty)), 2)

    def _cross_agent_consistency(
        self,
        state: PipelineState,
        findings: list[RiskFinding],
        disagreement_flags: list[str],
    ) -> float:
        if not findings:
            return 0.0
        score = 0.95
        if disagreement_flags:
            score -= min(0.45, 0.18 * len(disagreement_flags))
        if state.reflection_result:
            misclassified_count = sum(1 for issue in state.reflection_result.issues if issue.issue_type == "misclassified")
            severity_issue_count = sum(1 for issue in state.reflection_result.issues if issue.issue_type == "severity_issue")
            score -= min(0.2, 0.05 * misclassified_count)
            score -= min(0.2, 0.04 * severity_issue_count)
        return round(max(0.0, min(1.0, score)), 2)

    def _collect_disagreement_flags(self, state: PipelineState, findings: list[RiskFinding]) -> list[str]:
        flags: list[str] = []
        if state.reflection_result:
            for issue in state.reflection_result.issues:
                if "跨agent分歧" in issue.description:
                    flags.append(issue.description)
        for finding in findings:
            if finding.cross_agent_disagreement:
                flags.append(f"{finding.finding_id}:跨agent分歧")
        return sorted(set(flags))

    def _gate_flags(self, findings: list[RiskFinding]) -> GateFlags:
        reasons: list[str] = []
        for finding in findings:
            evidence = finding.evidence.lower()
            if (
                finding.category == "数据合规风险"
                and finding.severity == "high"
                and any(token in evidence for token in ["面部识别", "生物识别", "未明确告知", "境外", "跨境"])
            ):
                reasons.append(f"{finding.finding_id}:触发隐私/合法性红线")
            if (
                finding.category == "知识产权风险"
                and finding.severity == "high"
                and any(token in evidence for token in ["侵权", "泄密", "商业秘密"])
            ):
                reasons.append(f"{finding.finding_id}:触发合法性红线")
            if (
                finding.category in {"科技伦理风险", "算法安全风险"}
                and finding.severity in {"medium", "high"}
                and (
                    finding.category == "科技伦理风险"
                    or finding.subtype in {"算法操纵诱导", "群体信贷歧视", "费率定价公平"}
                    or any(token in evidence for token in ["歧视", "公平", "申诉", "操纵"])
                )
            ):
                reasons.append(f"{finding.finding_id}:触发伦理/公平红线")

        return GateFlags(
            privacy_legality_redline=any("隐私/合法性" in reason or "合法性红线" in reason for reason in reasons),
            ethics_fairness_redline=any("伦理/公平" in reason for reason in reasons),
            triggered_reasons=sorted(set(reasons)),
        )
