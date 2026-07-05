"""Stage 2 reflection agent."""

from __future__ import annotations

from risk_himate.app.core.analysis import flatten_findings, average_confidence
from risk_himate.app.core.schemas import PipelineState, ReflectionIssue, ReflectionResult, RiskFinding
from risk_himate.app.core.taxonomy import RISK_TAXONOMY
from risk_himate.app.llm.client import OpenAICompatibleLLMClient
from risk_himate.app.llm.prompting import load_prompt, to_pretty_json


SEVERITY_KEYWORDS = {
    "high": ["处罚", "违法", "侵权", "泄露", "跨境", "制裁", "封锁"],
    "medium": ["争议", "整改", "风险", "敏感"],
}

SEVERITY_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
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
        "medium": [
            "个人信息",
            "用户数据",
            "行为数据",
            "隐私",
            "数据安全",
            "数据存储",
        ],
    },
    "地缘博弈风险": {
        "high": ["制裁", "封锁", "出口管制", "实体清单"],
        "medium": ["海外客户", "海外市场", "出海", "境外监管", "数据主权", "境外服务器"],
    },
    "算法安全风险": {
        "high": ["算法歧视", "黑箱", "不可解释", "自动决策"],
        "medium": ["算法推荐", "推荐系统", "可解释性", "模型"],
    },
    "科技伦理风险": {
        "high": ["歧视", "人工干预机制缺失", "无法申诉", "缺乏人工干预"],
        "medium": ["透明度", "公平性", "问责", "伦理"],
    },
    "知识产权风险": {
        "high": ["侵权", "技术泄露", "商业秘密"],
        "medium": ["专利争议", "商标", "软著", "知识产权"],
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
                '      "suggested_subtype": "跨境数据传输",\n'
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
            if category_label == "数据合规风险" and any(token in lowered for token in ["跨境", "境外", "出境"]):
                return "跨境数据传输"
            if category_label == "算法安全风险" and any(token in lowered for token in ["可解释", "黑箱"]):
                return "算法黑箱"
            if category_label == "地缘博弈风险" and any(token in lowered for token in ["海外", "出海", "境外监管"]):
                return "出海合规壁垒"
            if category_label == "知识产权风险" and any(token in lowered for token in ["商标", "软著"]):
                return "软著/商标风险"
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
