"""Base company data collector interfaces."""

from __future__ import annotations

from risk_himate.app.core.schemas import AnalysisInput


class CompanyDataCollector:
    def collect(self, company_name: str, metadata: dict | None = None) -> AnalysisInput:
        raise NotImplementedError

    def is_configured(self) -> bool:
        return True
