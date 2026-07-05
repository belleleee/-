"""Local recommendation store with a future RAG-friendly interface."""

from __future__ import annotations

from pathlib import Path
import json

from risk_himate.app.core.schemas import RiskFinding


class RecommendationStore:
    def suggest_for_findings(self, findings: list[RiskFinding]) -> dict[str, str]:
        raise NotImplementedError


class LocalRecommendationStore(RecommendationStore):
    def __init__(self, seed_path: str | None = None) -> None:
        default_path = Path(__file__).resolve().parent / "seed_recommendations.json"
        self.seed_path = Path(seed_path) if seed_path else default_path
        self.recommendations = self._load_recommendations()

    def suggest_for_findings(self, findings: list[RiskFinding]) -> dict[str, str]:
        suggestions: dict[str, str] = {}
        for finding in findings:
            suggestions[finding.finding_id] = self._match_recommendation(finding)
        return suggestions

    def _load_recommendations(self) -> list[dict]:
        with self.seed_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _match_recommendation(self, finding: RiskFinding) -> str:
        for item in self.recommendations:
            if (
                item["category"] == finding.category
                and item["subtype"] == finding.subtype
                and item["severity"] == finding.severity
            ):
                return str(item["suggestion"])
        for item in self.recommendations:
            if item["category"] == finding.category and item["subtype"] == finding.subtype:
                return str(item["suggestion"])
        for item in self.recommendations:
            if item["category"] == finding.category:
                return str(item["suggestion"])
        return "建议结合企业内部治理流程进行专项排查，并补充可审计证据链。"
