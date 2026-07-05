"""Stage 3 revision agent."""

from __future__ import annotations

from copy import deepcopy

from risk_himate.app.core.schemas import PipelineState, ReflectionIssue, RiskFinding
from risk_himate.app.core.taxonomy import RISK_TAXONOMY
from risk_himate.app.llm.client import LLMError, OpenAICompatibleLLMClient
from risk_himate.app.llm.prompting import load_prompt, to_pretty_json


class RevisionAgent:
    def __init__(self, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        self.llm_client = llm_client

    def revise(self, state: PipelineState) -> dict[str, list[RiskFinding]]:
        if self.llm_client and self.llm_client.is_configured():
            try:
                return self._revise_with_llm(state)
            except Exception:
                return self._revise_with_rules(state)
        return self._revise_with_rules(state)

    def _revise_with_rules(self, state: PipelineState) -> dict[str, list[RiskFinding]]:
        revised = deepcopy(state.domain_findings)
        issues = state.reflection_result.issues if state.reflection_result else []

        for issue in issues:
            if issue.issue_type == "missing_risk":
                self._apply_missing_risk(revised, state, issue)
            elif issue.issue_type == "misclassified":
                self._apply_misclassification(revised, issue)
            elif issue.issue_type == "severity_issue":
                self._apply_severity_change(revised, issue)

        return revised

    def _revise_with_llm(self, state: PipelineState) -> dict[str, list[RiskFinding]]:
        revised_findings = deepcopy(state.domain_findings)
        prompt = load_prompt("revision")
        payload = self.llm_client.chat_json(
            system_prompt="你是 Risk-HiMATE 的修正 Agent，必须严格输出 JSON。",
            user_prompt=(
                f"{prompt}\n\n"
                "请只返回 JSON 对象，格式如下：\n"
                "{\n"
                '  "revised_findings": {\n'
                '    "数据合规风险": [\n'
                "      {\n"
                '        "finding_id": "data_compliance-chunk-001",\n'
                '        "category": "数据合规风险",\n'
                '        "subtype": "跨境数据传输",\n'
                '        "exists": true,\n'
                '        "severity": "high",\n'
                '        "confidence": 0.82,\n'
                '        "evidence_chunk_ids": ["chunk-001"],\n'
                '        "rationale": "说明",\n'
                '        "revision_reason": "修正原因"\n'
                "      }\n"
                "    ]\n"
                "  }\n"
                "}\n\n"
                f"chunks:\n{to_pretty_json([item.model_dump() for item in state.chunks])}\n\n"
                f"domain_findings:\n{to_pretty_json(state.domain_findings)}\n\n"
                f"reflection_issues:\n{to_pretty_json([item.model_dump() for item in (state.reflection_result.issues if state.reflection_result else [])])}"
            ),
        )
        chunks_by_id = {chunk.chunk_id: chunk for chunk in state.chunks}
        for category, raw_findings in payload.get("revised_findings", {}).items():
            revised_findings[category] = []
            for item in raw_findings:
                chunk_ids = item.get("evidence_chunk_ids", [])
                if not chunk_ids:
                    raise LLMError("Revision result requires evidence_chunk_ids.")
                chunk_id = chunk_ids[0]
                if chunk_id not in chunks_by_id:
                    raise LLMError(f"Unknown chunk_id returned by revision LLM: {chunk_id}")
                revised_findings[category].append(
                    RiskFinding(
                        finding_id=item.get("finding_id", f"revision-{category}-{chunk_id}"),
                        category=item.get("category", category),
                        subtype=item.get("subtype", "未指定"),
                        exists=bool(item.get("exists", True)),
                        severity=item.get("severity", "medium"),
                        confidence=float(item.get("confidence", 0.75)),
                        evidence=chunks_by_id[chunk_id].text,
                        evidence_chunk_ids=chunk_ids,
                        rationale=item.get("rationale", "LLM-generated revised finding."),
                        legal_basis=item.get("legal_basis", []),
                        revision_reason=item.get("revision_reason"),
                    )
                )
        return revised_findings

    def _apply_missing_risk(
        self,
        revised: dict[str, list[RiskFinding]],
        state: PipelineState,
        issue: ReflectionIssue,
    ) -> None:
        if not issue.suggested_category or not issue.chunk_id:
            return
        existing = revised.get(issue.suggested_category, [])
        if any(issue.chunk_id in finding.evidence_chunk_ids for finding in existing):
            return

        chunk = next((item for item in state.chunks if item.chunk_id == issue.chunk_id), None)
        if chunk is None:
            return

        metadata = next(
            (item for item in RISK_TAXONOMY.values() if item["label"] == issue.suggested_category),
            None,
        )
        if metadata is None:
            return

        finding = RiskFinding(
            finding_id=f"revision-{issue.chunk_id}-{issue.suggested_category}",
            category=issue.suggested_category,
            subtype=str(metadata["subtypes"][0]),
            exists=True,
            severity=issue.suggested_severity or "medium",
            confidence=max(0.45, issue.confidence),
            evidence=chunk.text,
            evidence_chunk_ids=[issue.chunk_id],
            rationale="Added during revision to cover a missing category flagged by reflection.",
            legal_basis=list(metadata["legal_basis"]),
            revision_reason=issue.description,
        )
        revised.setdefault(issue.suggested_category, []).append(finding)

    def _apply_misclassification(self, revised: dict[str, list[RiskFinding]], issue: ReflectionIssue) -> None:
        if not issue.related_finding_id:
            return
        for findings in revised.values():
            for finding in findings:
                if finding.finding_id != issue.related_finding_id:
                    continue
                if issue.suggested_subtype:
                    finding.subtype = issue.suggested_subtype
                finding.revision_reason = issue.description
                return

    def _apply_severity_change(self, revised: dict[str, list[RiskFinding]], issue: ReflectionIssue) -> None:
        if not issue.related_finding_id or not issue.suggested_severity:
            return
        for findings in revised.values():
            for finding in findings:
                if finding.finding_id != issue.related_finding_id:
                    continue
                finding.severity = issue.suggested_severity
                finding.revision_reason = issue.description
                return
