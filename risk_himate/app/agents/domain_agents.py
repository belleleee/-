"""Concrete risk-domain agents."""

from __future__ import annotations

from risk_himate.app.agents.base import BaseRiskAgent
from risk_himate.app.llm.client import OpenAICompatibleLLMClient


class AlgorithmSafetyAgent(BaseRiskAgent):
    def __init__(self, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        super().__init__("algorithm_safety", "algorithm", llm_client=llm_client)


class DataComplianceAgent(BaseRiskAgent):
    def __init__(self, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        super().__init__("data_compliance", "data_compliance", llm_client=llm_client)


class TechEthicsAgent(BaseRiskAgent):
    def __init__(self, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        super().__init__("tech_ethics", "ethics", llm_client=llm_client)


class IPRiskAgent(BaseRiskAgent):
    def __init__(self, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        super().__init__("ip_risk", "ip", llm_client=llm_client)


class GeopoliticalRiskAgent(BaseRiskAgent):
    def __init__(self, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        super().__init__("geopolitical", "geopolitics", llm_client=llm_client)
