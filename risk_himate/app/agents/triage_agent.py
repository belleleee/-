"""Stage 0 triage agent."""

from __future__ import annotations

from dataclasses import dataclass

from risk_himate.app.llm.client import OpenAICompatibleLLMClient, LLMError
from risk_himate.app.llm.prompting import load_prompt, to_pretty_json
from risk_himate.app.core.schemas import TextChunk, TriageResult
from risk_himate.app.core.taxonomy import RISK_TAXONOMY


@dataclass
class TriageConfig:
    relevance_threshold: float = 0.2


class TriageAgent:
    def __init__(
        self,
        config: TriageConfig | None = None,
        llm_client: OpenAICompatibleLLMClient | None = None,
    ) -> None:
        self.config = config or TriageConfig()
        self.llm_client = llm_client

    def analyze(self, chunks: list[TextChunk]) -> list[TriageResult]:
        if self.llm_client and self.llm_client.is_configured():
            try:
                return self._analyze_with_llm(chunks)
            except Exception:
                return self._analyze_with_rules(chunks)
        return self._analyze_with_rules(chunks)

    def _analyze_with_rules(self, chunks: list[TextChunk]) -> list[TriageResult]:
        results: list[TriageResult] = []
        for chunk in chunks:
            labels: list[str] = []
            max_score = 0.0
            matched_terms: list[str] = []
            text = chunk.text.lower()
            for meta in RISK_TAXONOMY.values():
                keywords = [keyword.lower() for keyword in meta["keywords"]]
                hits = [keyword for keyword in keywords if keyword in text]
                if hits:
                    labels.append(str(meta["label"]))
                    score = min(1.0, 0.25 + 0.18 * len(hits))
                    max_score = max(max_score, score)
                    matched_terms.extend(hits[:2])

            if labels and max_score >= self.config.relevance_threshold:
                results.append(
                    TriageResult(
                        chunk_id=chunk.chunk_id,
                        text=chunk.text,
                        candidate_risk_types=labels,
                        relevance_score=round(max_score, 2),
                        rationale=f"Matched keywords: {', '.join(sorted(set(matched_terms)))}",
                    )
                )
        return results

    def _analyze_with_llm(self, chunks: list[TextChunk]) -> list[TriageResult]:
        prompt = load_prompt("triage")
        taxonomy = {
            str(meta["label"]): list(meta["subtypes"])
            for meta in RISK_TAXONOMY.values()
        }
        user_prompt = (
            f"{prompt}\n\n"
            "请只返回 JSON 对象，格式如下：\n"
            "{\n"
            '  "results": [\n'
            "    {\n"
            '      "chunk_id": "chunk-001",\n'
            '      "candidate_risk_types": ["数据合规风险"],\n'
            '      "relevance_score": 0.85,\n'
            '      "rationale": "简短说明"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"风险 taxonomy：\n{to_pretty_json(taxonomy)}\n\n"
            f"文本块：\n{to_pretty_json([chunk.model_dump() for chunk in chunks])}"
        )
        payload = self.llm_client.chat_json(
            system_prompt="你是 Risk-HiMATE 的初评 Agent，必须严格输出 JSON。",
            user_prompt=user_prompt,
        )
        results: list[TriageResult] = []
        for item in payload.get("results", []):
            chunk_id = item.get("chunk_id")
            chunk = next((candidate for candidate in chunks if candidate.chunk_id == chunk_id), None)
            if chunk is None:
                raise LLMError(f"Unknown chunk_id returned by LLM triage: {chunk_id}")
            labels = item.get("candidate_risk_types", [])
            if not labels:
                continue
            results.append(
                TriageResult(
                    chunk_id=chunk_id,
                    text=chunk.text,
                    candidate_risk_types=labels,
                    relevance_score=float(item.get("relevance_score", 0.5)),
                    rationale=item.get("rationale", "LLM-generated triage result."),
                )
            )
        return results
