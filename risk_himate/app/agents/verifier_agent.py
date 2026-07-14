"""Stage 4 verifier agent."""

from __future__ import annotations

from risk_himate.app.core.analysis import flatten_findings
from risk_himate.app.core.schemas import PipelineState, VerificationResult
from risk_himate.app.llm.client import OpenAICompatibleLLMClient
from risk_himate.app.llm.prompting import load_prompt, to_pretty_json


class VerifierAgent:
    def __init__(self, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        self.llm_client = llm_client

    def verify(self, state: PipelineState) -> VerificationResult:
        if self.llm_client and self.llm_client.is_configured():
            try:
                return self._verify_with_llm(state)
            except Exception:
                return self._verify_with_rules(state)
        return self._verify_with_rules(state)

    def _verify_with_rules(self, state: PipelineState) -> VerificationResult:
        original_findings = flatten_findings(state.domain_findings)
        revised_findings = flatten_findings(state.revised_findings)
        issues = state.reflection_result.issues if state.reflection_result else []
        confidence_result = state.confidence_result

        resolved = 0
        accepted_ids: list[str] = []
        rejected_ids: list[str] = []

        for issue in issues:
            if issue.issue_type == "missing_risk":
                matched = [
                    finding for finding in revised_findings
                    if issue.chunk_id in finding.evidence_chunk_ids and finding.category == issue.suggested_category
                ]
                if matched:
                    resolved += 1
                    accepted_ids.extend([finding.finding_id for finding in matched])
            else:
                matched = next(
                    (finding for finding in revised_findings if finding.finding_id == issue.related_finding_id),
                    None,
                )
                if matched is None:
                    continue
                if issue.issue_type == "misclassified" and issue.suggested_subtype == matched.subtype:
                    resolved += 1
                    accepted_ids.append(matched.finding_id)
                elif issue.issue_type == "severity_issue" and issue.suggested_severity == matched.severity:
                    resolved += 1
                    accepted_ids.append(matched.finding_id)

        resolution_rate = 1.0 if not issues else resolved / len(issues)
        confidence_score = confidence_result.confidence_score if confidence_result else 0.7
        confidence = round(min(0.98, max(0.0, 0.5 * resolution_rate + 0.5 * confidence_score)), 2)

        if resolution_rate >= 0.85:
            verdict = "accept"
        elif resolution_rate >= 0.4:
            verdict = "partial_accept"
        else:
            verdict = "revert_to_original"

        gate_triggered = False
        gate_reasons: list[str] = []
        if confidence_result:
            gate_triggered = (
                confidence_result.gate_flags.privacy_legality_redline
                or confidence_result.gate_flags.ethics_fairness_redline
            )
            gate_reasons = confidence_result.gate_flags.triggered_reasons

        if verdict == "accept" and confidence_score < 0.55:
            verdict = "partial_accept"
        if verdict == "accept" and gate_triggered:
            verdict = "partial_accept"
        if verdict == "partial_accept" and confidence_score < 0.35 and resolution_rate < 0.55:
            verdict = "revert_to_original"

        original_ids = {finding.finding_id for finding in original_findings}
        revised_ids = {finding.finding_id for finding in revised_findings}
        has_cross_agent_disagreement = any(
            finding.cross_agent_disagreement
            or ("跨agent分歧" in (finding.revision_reason or ""))
            for finding in revised_findings
        )
        if verdict == "revert_to_original":
            rejected_ids = sorted(list(revised_ids - original_ids))
        else:
            rejected_ids = sorted(
                {
                    issue.related_finding_id
                    for issue in issues
                    if issue.related_finding_id and issue.related_finding_id not in accepted_ids
                }
            )

        notes = (
            "Revisions fully addressed reflected issues."
            if verdict == "accept"
            else "Revisions addressed part of the reflected issues."
            if verdict == "partial_accept"
            else "Revisions did not sufficiently resolve reflected issues."
        )
        if confidence_result:
            notes += f" confidence_score={confidence_score:.2f}."
        if gate_reasons:
            notes += f" gate_flags={'; '.join(gate_reasons)}."

        return VerificationResult(
            verdict=verdict,
            confidence=confidence,
            accepted_finding_ids=sorted(set(accepted_ids)),
            rejected_finding_ids=rejected_ids,
            needs_human_review=confidence_score < 0.6 or has_cross_agent_disagreement or gate_triggered,
            notes=notes,
        )

    def _verify_with_llm(self, state: PipelineState) -> VerificationResult:
        prompt = load_prompt("verifier")
        payload = self.llm_client.chat_json(
            system_prompt="你是 Risk-HiMATE 的核验 Agent，必须严格输出 JSON。",
            user_prompt=(
                f"{prompt}\n\n"
                "请只返回 JSON 对象，格式如下：\n"
                "{\n"
                '  "verdict": "accept|partial_accept|revert_to_original",\n'
                '  "confidence": 0.85,\n'
                '  "accepted_finding_ids": ["id1"],\n'
                '  "rejected_finding_ids": ["id2"],\n'
                '  "needs_human_review": false,\n'
                '  "notes": "说明"\n'
                "}\n\n"
                f"confidence_result:\n{to_pretty_json(state.confidence_result.model_dump() if state.confidence_result else {})}\n\n"
                f"original_findings:\n{to_pretty_json(state.domain_findings)}\n\n"
                f"reflection_issues:\n{to_pretty_json([item.model_dump() for item in (state.reflection_result.issues if state.reflection_result else [])])}\n\n"
                f"revised_findings:\n{to_pretty_json(state.revised_findings)}"
            ),
        )
        return VerificationResult(
            verdict=payload.get("verdict", "partial_accept"),
            confidence=float(payload.get("confidence", 0.7)),
            accepted_finding_ids=payload.get("accepted_finding_ids", []),
            rejected_finding_ids=payload.get("rejected_finding_ids", []),
            needs_human_review=bool(payload.get("needs_human_review", False)),
            notes=payload.get("notes", "LLM-generated verification result."),
        )
