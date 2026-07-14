"""Stage 2 reflection agent."""

from __future__ import annotations

from risk_himate.app.core.analysis import average_confidence, flatten_findings, severity_gap
from risk_himate.app.core.schemas import PipelineState, ReflectionIssue, ReflectionResult, RiskFinding
from risk_himate.app.core.taxonomy import RISK_TAXONOMY
from risk_himate.app.llm.client import OpenAICompatibleLLMClient
from risk_himate.app.llm.prompting import load_prompt, to_pretty_json


SEVERITY_KEYWORDS = {
    "high": ["处罚", "违法", "侵权", "泄露", "跨境", "制裁", "封锁"],
    "medium": ["争议", "整改", "风险", "敏感"],
}

CATEGORY_SEVERITY_SIGNALS = {
    "数据合规风险": {
        "high": [
            "面部识别",
            "生物识别",
            "敏感个人信息",
            "未向用户明确告知",
            "未明确告知",
            "未告知用户",
            "境外服务器",
            "境外存储",
            "跨境",
            "出境",
        ],
        "medium": ["个人信息", "用户数据", "行为数据", "隐私", "数据安全", "数据存储", "第三方共享"],
    },
    "地缘博弈风险": {
        "high": ["制裁", "出口管制", "实体清单", "外国投资审查", "受限方"],
        "medium": ["海外客户", "海外市场", "出海", "境外监管", "数据主权", "境外服务器", "技术转移"],
    },
    "算法安全风险": {
        "high": ["诱导", "操纵", "失控", "故障", "对抗样本", "越狱"],
        "medium": ["算法推荐", "推荐系统", "模型", "自动决策", "滥用"],
    },
    "科技伦理风险": {
        "high": ["歧视", "无法申诉", "缺乏人工干预", "不可追溯"],
        "medium": ["透明度", "公平性", "问责", "伦理", "模型迭代", "费率"],
    },
    "知识产权风险": {
        "high": ["侵权", "技术泄露", "商业秘密", "泄密"],
        "medium": ["专利争议", "开源", "许可证", "知识产权", "权属"],
    },
}


class ReflectionAgent:
    def __init__(self, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        self.llm_client = llm_client

    def analyze(self, state: PipelineState) -> ReflectionResult:
        if self.llm_client and self.llm_client.is_configured():
            try:
                return self._analyze_with_llm(state)
            except Exception:
                return self._analyze_with_rules(state)
        return self._analyze_with_rules(state)

    def _analyze_with_rules(self, state: PipelineState) -> ReflectionResult:
        issues: list[ReflectionIssue] = []
        findings = flatten_findings(state.domain_findings)

        issues.extend(self._find_missing_risks(state))
        issues.extend(self._find_subtype_issues(findings))
        issues.extend(self._find_severity_issues(findings))
        issues.extend(self._find_cross_agent_disagreements(findings))

        confidence = average_confidence(findings)
        summary = (
            "No reflection issues found." if not issues
            else f"Detected {len(issues)} issue(s) across missing risk, subtype, or severity checks."
        )
        return ReflectionResult(
            issues=issues,
            overall_confidence=confidence,
            summary=summary,
        )

    def _analyze_with_llm(self, state: PipelineState) -> ReflectionResult:
        prompt = load_prompt("reflection")
        payload = self.llm_client.chat_json(
            system_prompt="你是 Risk-HiMATE 的反思 Agent，必须严格输出 JSON。",
            user_prompt=(
                f"{prompt}\n\n"
                "请只返回 JSON 对象，格式如下：\n"
                "{\n"
                '  "issues": [\n'
                "    {\n"
                '      "issue_id": "issue-1",\n'
                '      "issue_type": "missing_risk|misclassified|severity_issue",\n'
                '      "category": "数据合规风险",\n'
                '      "chunk_id": "chunk-001",\n'
                '      "related_finding_id": "data_compliance-chunk-001",\n'
                '      "description": "说明",\n'
                '      "suggested_fix": "修正建议",\n'
                '      "suggested_category": "数据合规风险",\n'
                '      "suggested_subtype": "数据共享与出境",\n'
                '      "suggested_severity": "high",\n'
                '      "confidence": 0.8\n'
                "    }\n"
                "  ],\n"
                '  "summary": "总结",\n'
                '  "overall_confidence": 0.8\n'
                "}\n\n"
                f"triage_results:\n{to_pretty_json([item.model_dump() for item in state.triage_results])}\n\n"
                f"domain_findings:\n{to_pretty_json(state.domain_findings)}"
            ),
        )
        return ReflectionResult(
            issues=[ReflectionIssue(**item) for item in payload.get("issues", [])],
            overall_confidence=float(payload.get("overall_confidence", average_confidence(flatten_findings(state.domain_findings)))),
            summary=payload.get("summary", "LLM reflection summary."),
        )

    def _find_missing_risks(self, state: PipelineState) -> list[ReflectionIssue]:
        issues: list[ReflectionIssue] = []
        existing_categories = {
            category
            for category, findings in state.domain_findings.items()
            if findings
        }
        for triage in state.triage_results:
            for label in triage.candidate_risk_types:
                if label in existing_categories:
                    continue
                issues.append(
                    ReflectionIssue(
                        issue_id=f"missing-{label}-{triage.chunk_id}",
                        issue_type="missing_risk",
                        category=label,
                        chunk_id=triage.chunk_id,
                        description=f"Triage marked {label} for {triage.chunk_id}, but no domain finding was produced.",
                        suggested_fix="Add a finding for the missing category using the same evidence chunk.",
                        suggested_category=label,
                        confidence=max(0.5, triage.relevance_score),
                    )
                )
        return issues

    def _find_subtype_issues(self, findings: list[RiskFinding]) -> list[ReflectionIssue]:
        issues: list[ReflectionIssue] = []
        for finding in findings:
            suggested_subtype = self._infer_subtype(finding.category, finding.evidence)
            if suggested_subtype and suggested_subtype != finding.subtype:
                issues.append(
                    ReflectionIssue(
                        issue_id=f"subtype-{finding.finding_id}",
                        issue_type="misclassified",
                        category=finding.category,
                        related_finding_id=finding.finding_id,
                        chunk_id=finding.evidence_chunk_ids[0] if finding.evidence_chunk_ids else None,
                        description=f"Finding {finding.finding_id} may be better labeled as {suggested_subtype}.",
                        suggested_fix="Update the subtype to better align with the evidence text.",
                        suggested_subtype=suggested_subtype,
                        confidence=max(0.45, finding.confidence - 0.05),
                    )
                )
        return issues

    def _find_severity_issues(self, findings: list[RiskFinding]) -> list[ReflectionIssue]:
        issues: list[ReflectionIssue] = []
        for finding in findings:
            inferred = self._infer_severity(finding.category, finding.evidence)
            if inferred != finding.severity:
                issues.append(
                    ReflectionIssue(
                        issue_id=f"severity-{finding.finding_id}",
                        issue_type="severity_issue",
                        category=finding.category,
                        related_finding_id=finding.finding_id,
                        chunk_id=finding.evidence_chunk_ids[0] if finding.evidence_chunk_ids else None,
                        description=f"Finding {finding.finding_id} severity may be {inferred} instead of {finding.severity}.",
                        suggested_fix="Adjust severity to align with evidence strength.",
                        suggested_severity=inferred,
                        confidence=max(0.4, finding.confidence - 0.1),
                    )
                )
        return issues

    def _infer_subtype(self, category_label: str, evidence: str) -> str | None:
        lowered = evidence.lower()
        for metadata in RISK_TAXONOMY.values():
            if metadata["label"] != category_label:
                continue
            for subtype in metadata["subtypes"]:
                subtype_keywords = [token for token in subtype.replace("/", " ").split() if token]
                if any(token.lower() in lowered for token in subtype_keywords):
                    return str(subtype)
            if category_label == "数据合规风险" and any(token in lowered for token in ["跨境", "境外", "出境", "第三方共享"]):
                return "数据共享与出境"
            if category_label == "算法安全风险" and any(token in lowered for token in ["诱导", "操纵", "推荐"]):
                return "算法操纵诱导"
            if category_label == "算法安全风险" and any(token in lowered for token in ["失控", "故障", "异常输出"]):
                return "模型失控故障"
            if category_label == "科技伦理风险" and any(token in lowered for token in ["可解释", "透明"]):
                return "全局模型可解释"
            if category_label == "地缘博弈风险" and any(token in lowered for token in ["实体清单", "受限方", "制裁"]):
                return "实体清单/受限方清单"
            if category_label == "地缘博弈风险" and any(token in lowered for token in ["出口管制", "两用物项"]):
                return "出口管制物项动态纳入"
            if category_label == "知识产权风险" and any(token in lowered for token in ["开源", "许可证", "gpl", "apache", "mit"]):
                return "开源软件合规"
            if category_label == "知识产权风险" and any(token in lowered for token in ["权属", "职务发明", "研发人员"]):
                return "职务发明权属争议"
        return None

    def _infer_severity(self, category_label: str, evidence: str) -> str:
        lowered = evidence.lower()
        category_signals = CATEGORY_SEVERITY_SIGNALS.get(category_label, {})
        high_hits = [
            token for token in category_signals.get("high", [])
            if token.lower() in lowered
        ]
        medium_hits = [
            token for token in category_signals.get("medium", [])
            if token.lower() in lowered
        ]

        if category_label == "数据合规风险":
            has_sensitive_data = any(token in lowered for token in ["面部识别", "生物识别", "敏感个人信息"])
            has_cross_border = any(token in lowered for token in ["跨境", "出境", "境外服务器", "境外存储"])
            has_notice_gap = any(token in lowered for token in ["未向用户明确告知", "未明确告知", "未告知用户"])
            if sum([has_sensitive_data, has_cross_border, has_notice_gap]) >= 2:
                return "high"

        if len(high_hits) >= 2:
            return "high"
        if high_hits and medium_hits:
            return "high"
        if high_hits:
            return "medium"
        if medium_hits:
            return "medium"

        if any(token in lowered for token in SEVERITY_KEYWORDS["high"]):
            return "high"
        if any(token in lowered for token in SEVERITY_KEYWORDS["medium"]):
            return "medium"
        return "low"

    def _find_cross_agent_disagreements(self, findings: list[RiskFinding]) -> list[ReflectionIssue]:
        issues: list[ReflectionIssue] = []
        for index, finding in enumerate(findings):
            for other in findings[index + 1:]:
                if finding.category == other.category:
                    continue
                if not self._share_fact_basis(finding, other):
                    continue
                if severity_gap(finding.severity, other.severity) < 2:
                    continue

                lower, higher = (
                    (finding, other)
                    if finding.severity != "high"
                    else (other, finding)
                )
                issues.append(
                    ReflectionIssue(
                        issue_id=f"cross-severity-{lower.finding_id}",
                        issue_type="severity_issue",
                        category=lower.category,
                        related_finding_id=lower.finding_id,
                        chunk_id=lower.evidence_chunk_ids[0] if lower.evidence_chunk_ids else None,
                        description=(
                            f"Finding {lower.finding_id} 与 {higher.finding_id} 对同一事实存在跨agent分歧，"
                            "当前按较高严重度处理。"
                        ),
                        suggested_fix="将较低严重度提升到跨agent比较中的较高值，并提高人工复核优先级。",
                        suggested_severity=higher.severity,
                        confidence=max(0.5, min(higher.confidence, 0.9)),
                    )
                )
        return issues

    def _share_fact_basis(self, left: RiskFinding, right: RiskFinding) -> bool:
        if set(left.evidence_chunk_ids) & set(right.evidence_chunk_ids):
            return True
        return left.evidence == right.evidence
