"""Offline-friendly company profile collector."""

from __future__ import annotations

from pathlib import Path
import json

from risk_himate.app.core.schemas import AnalysisInput
from risk_himate.app.data_sources.base import CompanyDataCollector


DEFAULT_LOCAL_DATA_PATH = Path(__file__).resolve().parent / "mock_company_data.json"


class LocalCompanyDataCollector(CompanyDataCollector):
    def __init__(self, data_path: str | None = None) -> None:
        self.data_path = Path(data_path) if data_path else DEFAULT_LOCAL_DATA_PATH
        self.records = self._load_records()

    def collect(self, company_name: str, metadata: dict | None = None) -> AnalysisInput:
        merged_metadata = dict(metadata or {})
        company_record = self.records.get(company_name, {})
        merged_metadata.update(company_record)
        if "company_name" not in merged_metadata:
            merged_metadata["company_name"] = company_name
        raw_text = build_company_profile_text(company_name, merged_metadata)
        return AnalysisInput(
            input_type="company_name",
            company_name=company_name,
            raw_text=raw_text,
            metadata=merged_metadata,
        )

    def _load_records(self) -> dict[str, dict]:
        if not self.data_path.exists():
            return {}
        return json.loads(self.data_path.read_text(encoding="utf-8"))


def build_company_profile_text(company_name: str, metadata: dict) -> str:
    sections: list[str] = [f"企业名称：{company_name}。"]
    alias = metadata.get("alias")
    if alias:
        sections.append(f"企业简称：{alias}。")
    description = metadata.get("description")
    if description:
        sections.append(f"企业简介：{description}。")
    sectors = metadata.get("sectors", [])
    if sectors:
        sections.append(f"业务领域：{'、'.join(sectors)}。")
    products = metadata.get("products", [])
    if products:
        sections.append(f"核心产品：{'、'.join(products)}。")
    operations = metadata.get("operations", [])
    if operations:
        sections.append(f"经营与技术情况：{'；'.join(operations)}。")
    risks = metadata.get("risk_signals", [])
    if risks:
        sections.append(f"公开风险信号：{'；'.join(risks)}。")
    governance = metadata.get("governance_notes", [])
    if governance:
        sections.append(f"治理与合规说明：{'；'.join(governance)}。")
    source_notes = metadata.get("source_notes", [])
    if source_notes:
        sections.append(f"数据来源摘要：{'；'.join(source_notes)}。")
    return "\n".join(sections)
