"""Base agent abstractions."""

from __future__ import annotations

import re

from risk_himate.app.core.schemas import RiskFinding, TextChunk, TriageResult
from risk_himate.app.core.taxonomy import RISK_TAXONOMY, SUBTYPE_STAGE_FALLBACK
from risk_himate.app.llm.client import LLMError, OpenAICompatibleLLMClient
from risk_himate.app.llm.prompting import load_prompt, to_pretty_json


class BaseRiskAgent:
    def __init__(
        self,
        category_code: str,
        prompt_name: str | None = None,
        llm_client: OpenAICompatibleLLMClient | None = None,
    ) -> None:
        if category_code not in RISK_TAXONOMY:
            raise ValueError(f"Unknown category_code: {category_code}")
        self.category_code = category_code
        self.category_meta = RISK_TAXONOMY[category_code]
        self.prompt_name = prompt_name or category_code
        self.llm_client = llm_client

    @property
    def category_label(self) -> str:
        return str(self.category_meta["label"])

    @property
    def subtypes(self) -> list[str]:
        return list(self.category_meta["subtypes"])

    @property
    def legal_basis(self) -> list[str]:
        return list(self.category_meta["legal_basis"])

    @property
    def keywords(self) -> list[str]:
        return list(self.category_meta["keywords"])

    def load_prompt(self) -> str:
        return load_prompt(self.prompt_name)

    def analyze(self, triage_results: list[TriageResult], chunks_by_id: dict[str, TextChunk]) -> list[RiskFinding]:
        if self.llm_client and self.llm_client.is_configured():
            try:
                return self._analyze_with_llm(triage_results, chunks_by_id)
            except Exception:
                return self._analyze_with_rules(triage_results, chunks_by_id)
        return self._analyze_with_rules(triage_results, chunks_by_id)

    def _analyze_with_rules(self, triage_results: list[TriageResult], chunks_by_id: dict[str, TextChunk]) -> list[RiskFinding]:
        findings: list[RiskFinding] = []
        for triage_result in triage_results:
            if self.category_label not in triage_result.candidate_risk_types:
                continue
            subtype = self.select_subtype(triage_result.text)
            findings.append(
                RiskFinding(
                    finding_id=f"{self.category_code}-{triage_result.chunk_id}",
                    category=self.category_label,
                    subtype=subtype,
                    exists=True,
                    severity=self.estimate_severity(triage_result.text),
                    confidence=max(0.45, min(0.95, triage_result.relevance_score)),
                    evidence=chunks_by_id[triage_result.chunk_id].text,
                    evidence_chunk_ids=[triage_result.chunk_id],
                    rationale=f"Matched category keywords for {self.category_label}.",
                    legal_basis=self.legal_basis,
                    trigger_signal_matched=self.match_trigger_signals(chunks_by_id[triage_result.chunk_id].text, subtype),
                    related_category_hint=self.related_category_hints(chunks_by_id[triage_result.chunk_id].text),
                    lifecycle_stage_hint=self.lifecycle_stage_hint(subtype, chunks_by_id[triage_result.chunk_id].text),
                )
            )
        return findings

    def _analyze_with_llm(self, triage_results: list[TriageResult], chunks_by_id: dict[str, TextChunk]) -> list[RiskFinding]:
        relevant_triage = [
            triage for triage in triage_results
            if self.category_label in triage.candidate_risk_types
        ]
        if not relevant_triage:
            return []
        prompt = self.load_prompt()
        evidence_payload = [
            {
                "chunk_id": triage.chunk_id,
                "text": chunks_by_id[triage.chunk_id].text,
                "relevance_score": triage.relevance_score,
                "candidate_risk_types": triage.candidate_risk_types,
            }
            for triage in relevant_triage
        ]
        user_prompt = (
            f"{prompt}\n\n"
            f"你负责的风险类别：{self.category_label}\n"
            f"子类型：{', '.join(self.subtypes)}\n"
            f"法规依据：{', '.join(self.legal_basis)}\n\n"
            "请只返回 JSON 对象，格式如下：\n"
            "{\n"
            '  "findings": [\n'
            "    {\n"
            '      "chunk_id": "chunk-001",\n'
            f'      "category": "{self.category_label}",\n'
            f'      "subtype": "{self.subtypes[0]}",\n'
            '      "exists": true,\n'
            '      "severity": "low|medium|high",\n'
            '      "confidence": 0.0,\n'
            '      "trigger_signal_matched": ["信号词1"],\n'
            '      "related_category_hint": ["可能关联的其他类别"],\n'
            '      "lifecycle_stage_hint": "技术研发|数据运营|场景落地|商业出海",\n'
            '      "rationale": "简短说明"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"证据文本：\n{to_pretty_json(evidence_payload)}"
        )
        payload = self.llm_client.chat_json(
            system_prompt="你是 Risk-HiMATE 的风险识别领域专家，必须严格输出 JSON。",
            user_prompt=user_prompt,
        )
        raw_findings = payload.get("findings", [])
        findings: list[RiskFinding] = []
        for item in raw_findings:
            if not item.get("exists", True):
                continue
            chunk_id = item.get("chunk_id")
            if chunk_id not in chunks_by_id:
                raise LLMError(f"Unknown chunk_id returned by LLM: {chunk_id}")
            findings.append(
                RiskFinding(
                    finding_id=f"{self.category_code}-{chunk_id}",
                    category=item.get("category", self.category_label),
                    subtype=item.get("subtype", self.subtypes[0]),
                    exists=bool(item.get("exists", True)),
                    severity=item.get("severity", self.estimate_severity(chunks_by_id[chunk_id].text)),
                    confidence=float(item.get("confidence", 0.7)),
                    evidence=chunks_by_id[chunk_id].text,
                    evidence_chunk_ids=[chunk_id],
                    rationale=item.get("rationale", "LLM-generated risk finding."),
                    legal_basis=self.legal_basis,
                    trigger_signal_matched=item.get("trigger_signal_matched", self.match_trigger_signals(chunks_by_id[chunk_id].text, item.get("subtype", self.subtypes[0]))),
                    related_category_hint=item.get("related_category_hint", self.related_category_hints(chunks_by_id[chunk_id].text)),
                    lifecycle_stage_hint=item.get("lifecycle_stage_hint", self.lifecycle_stage_hint(item.get("subtype", self.subtypes[0]), chunks_by_id[chunk_id].text)),
                )
            )
        return findings

    def select_subtype(self, text: str) -> str:
        lowered = text.lower()
        subtype_keywords = {}
        signal_map = self.category_meta.get("subtype_signals", {})
        for subtype in self.subtypes:
            tokens = [token.lower() for token in re.split(r"[、/ ]+", subtype) if token]
            tokens.extend(token.lower() for token in signal_map.get(subtype, []))
            subtype_keywords[subtype] = tokens
        for subtype, tokens in subtype_keywords.items():
            if any(token in lowered for token in tokens):
                return subtype
        return self.subtypes[0]

    def estimate_severity(self, text: str) -> str:
        severity_rules = {
            "high": ["违法", "处罚", "泄露", "侵权", "跨境", "制裁", "封锁"],
            "medium": ["风险", "整改", "争议", "投诉", "敏感"],
        }
        lowered = text.lower()
        if any(token in lowered for token in severity_rules["high"]):
            return "high"
        if any(token in lowered for token in severity_rules["medium"]):
            return "medium"
        return "low"

    def match_trigger_signals(self, text: str, subtype: str) -> list[str]:
        lowered = text.lower()
        matched: list[str] = []
        for token in self.category_meta.get("subtype_signals", {}).get(subtype, []):
            if token.lower() in lowered:
                matched.append(token)
        return matched

    def related_category_hints(self, text: str) -> list[str]:
        lowered = text.lower()
        hints: list[str] = []
        if self.category_label == "数据合规风险" and any(token in lowered for token in ["跨境", "出境", "境外", "海外"]):
            hints.append("地缘博弈风险")
        if self.category_label == "算法安全风险" and any(token in lowered for token in ["公平", "歧视", "透明", "解释", "申诉"]):
            hints.append("科技伦理风险")
        if self.category_label == "科技伦理风险" and any(token in lowered for token in ["用户数据", "个人信息", "隐私"]):
            hints.append("数据合规风险")
        return hints

    def lifecycle_stage_hint(self, subtype: str, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ["出海", "海外", "境外", "出口管制", "外国投资"]):
            return "商业出海"
        if any(token in lowered for token in ["研发", "训练", "模型迭代", "参数", "源代码", "专利"]):
            return "技术研发"
        if any(token in lowered for token in ["用户数据", "存储", "共享", "授权", "采集", "日志"]):
            return "数据运营"
        if any(token in lowered for token in ["投放", "推荐", "定价", "授信", "审核", "申诉"]):
            return "场景落地"
        return SUBTYPE_STAGE_FALLBACK.get(subtype, "场景落地")
