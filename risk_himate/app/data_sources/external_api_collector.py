"""External API-backed company data collector."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from hashlib import md5
import json
import os
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from risk_himate.app.core.schemas import AnalysisInput
from risk_himate.app.data_sources.base import CompanyDataCollector
from risk_himate.app.data_sources.company_profile_collector import (
    LocalCompanyDataCollector,
    build_company_profile_text,
)


class CollectorConfigurationError(RuntimeError):
    """Raised when an external collector is not properly configured."""


def default_json_transport(url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = Request(url=url, headers=headers, method="GET")
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


@dataclass
class QCCOpenAPIClient:
    app_key: str
    secret_key: str
    transport: Callable[[str, dict[str, str]], dict[str, Any]] = default_json_transport
    base_url: str = "https://api.qichacha.com"

    def get_basic_details_by_name(self, company_name: str) -> dict[str, Any]:
        return self._request(
            "/ECIV4/GetBasicDetailsByName",
            {"key": self.app_key, "keyword": company_name},
        )

    def get_patents(self, company_name: str, page_size: int = 10) -> dict[str, Any]:
        return self._request(
            "/PatentV4/Search",
            {"key": self.app_key, "searchKey": company_name, "pageSize": str(page_size), "pageIndex": "1"},
        )

    def get_judgments(self, company_name: str, page_size: int = 10) -> dict[str, Any]:
        return self._request(
            "/JudgmentDocCheck/GetList",
            {"key": self.app_key, "searchKey": company_name, "pageSize": str(page_size), "pageIndex": "1"},
        )

    def _request(self, path: str, query: dict[str, str]) -> dict[str, Any]:
        timespan = str(int(datetime.now(UTC).timestamp()))
        token = md5(f"{self.app_key}{timespan}{self.secret_key}".encode("utf-8")).hexdigest().upper()
        headers = {
            "Token": token,
            "Timespan": timespan,
        }
        url = f"{self.base_url}{path}?{urlencode(query)}"
        return self.transport(url, headers)


@dataclass
class NewsAPIClient:
    api_key: str
    transport: Callable[[str, dict[str, str]], dict[str, Any]] = default_json_transport
    base_url: str = "https://newsapi.org/v2"

    def search_company_news(
        self,
        company_name: str,
        language: str = "zh",
        lookback_days: int = 30,
        page_size: int = 5,
    ) -> dict[str, Any]:
        start_date = (datetime.now(UTC) - timedelta(days=lookback_days)).date().isoformat()
        query = {
            "q": f"\"{company_name}\"",
            "language": language,
            "sortBy": "publishedAt",
            "pageSize": str(page_size),
            "from": start_date,
        }
        url = f"{self.base_url}/everything?{urlencode(query)}"
        headers = {"X-Api-Key": self.api_key}
        return self.transport(url, headers)


class ExternalCompanyDataCollector(CompanyDataCollector):
    def __init__(
        self,
        qcc_client: QCCOpenAPIClient | None = None,
        news_client: NewsAPIClient | None = None,
        fallback_collector: CompanyDataCollector | None = None,
    ) -> None:
        self.qcc_client = qcc_client
        self.news_client = news_client
        self.fallback_collector = fallback_collector or LocalCompanyDataCollector()

    @classmethod
    def from_env(cls, fallback_collector: CompanyDataCollector | None = None) -> "ExternalCompanyDataCollector":
        qcc_key = os.getenv("QCC_APP_KEY")
        qcc_secret = os.getenv("QCC_SECRET_KEY")
        news_api_key = os.getenv("NEWSAPI_KEY")
        qcc_client = QCCOpenAPIClient(qcc_key, qcc_secret) if qcc_key and qcc_secret else None
        news_client = NewsAPIClient(news_api_key) if news_api_key else None
        return cls(
            qcc_client=qcc_client,
            news_client=news_client,
            fallback_collector=fallback_collector,
        )

    def is_configured(self) -> bool:
        return self.qcc_client is not None or self.news_client is not None

    def collect(self, company_name: str, metadata: dict | None = None) -> AnalysisInput:
        merged_metadata = dict(metadata or {})
        source_notes = list(merged_metadata.get("source_notes", []))
        provider_errors: list[str] = []
        has_external_data = False

        if self.qcc_client is not None:
            try:
                self._merge_qcc_data(company_name, merged_metadata)
                has_external_data = True
                source_notes.append("企查查开放平台：工商/裁判文书/专利数据")
            except Exception as exc:  # noqa: BLE001
                provider_errors.append(f"QCC: {exc}")

        if self.news_client is not None:
            try:
                self._merge_news_data(company_name, merged_metadata)
                has_external_data = True
                source_notes.append("NewsAPI：新闻舆情数据")
            except Exception as exc:  # noqa: BLE001
                provider_errors.append(f"NewsAPI: {exc}")

        if provider_errors:
            merged_metadata["collector_errors"] = provider_errors

        if not has_external_data:
            fallback_input = self.fallback_collector.collect(company_name, merged_metadata)
            fallback_input.metadata["collector_mode"] = "fallback_local"
            return fallback_input

        merged_metadata["company_name"] = company_name
        merged_metadata["source_notes"] = source_notes
        merged_metadata["collector_mode"] = "external_api"
        return AnalysisInput(
            input_type="company_name",
            company_name=company_name,
            raw_text=build_company_profile_text(company_name, merged_metadata),
            metadata=merged_metadata,
        )

    def _merge_qcc_data(self, company_name: str, metadata: dict) -> None:
        basic = self.qcc_client.get_basic_details_by_name(company_name)
        patents = self.qcc_client.get_patents(company_name)
        judgments = self.qcc_client.get_judgments(company_name)

        self._merge_qcc_basic_details(metadata, basic)
        self._merge_qcc_patents(metadata, patents)
        self._merge_qcc_judgments(metadata, judgments)

    def _merge_qcc_basic_details(self, metadata: dict, payload: dict[str, Any]) -> None:
        data = self._unwrap_payload(payload)
        if not data:
            return
        metadata.setdefault("description", data.get("Scope") or data.get("Name") or "")
        sectors = list(metadata.get("sectors", []))
        if data.get("EconKind"):
            sectors.append(str(data["EconKind"]))
        metadata["sectors"] = _dedupe(sectors)

        operations = list(metadata.get("operations", []))
        if data.get("Scope"):
            operations.append(f"经营范围包括：{data['Scope']}")
        if data.get("Address"):
            operations.append(f"注册地址：{data['Address']}")
        if data.get("OperName"):
            operations.append(f"法定代表人：{data['OperName']}")
        if data.get("Status"):
            operations.append(f"登记状态：{data['Status']}")
        if data.get("IsOnStock") == "1":
            operations.append(f"上市类型：{data.get('StockType', '已上市')}")
        metadata["operations"] = _dedupe(operations)

        governance = list(metadata.get("governance_notes", []))
        if data.get("CreditCode"):
            governance.append(f"统一社会信用代码：{data['CreditCode']}")
        if data.get("TermEnd"):
            governance.append(f"营业期限至：{data['TermEnd']}")
        metadata["governance_notes"] = _dedupe(governance)

    def _merge_qcc_patents(self, metadata: dict, payload: dict[str, Any]) -> None:
        data = self._unwrap_payload(payload)
        if not data:
            return
        patent_items = data if isinstance(data, list) else data.get("Data") if isinstance(data, dict) else []
        if not patent_items:
            return
        risk_signals = list(metadata.get("risk_signals", []))
        top_titles = [
            item.get("Title")
            for item in patent_items[:3]
            if isinstance(item, dict) and item.get("Title")
        ]
        if top_titles:
            risk_signals.append(f"专利检索命中：{'；'.join(top_titles)}")
        metadata["risk_signals"] = _dedupe(risk_signals)
        metadata["products"] = _dedupe(list(metadata.get("products", [])) + top_titles[:2])

    def _merge_qcc_judgments(self, metadata: dict, payload: dict[str, Any]) -> None:
        data = self._unwrap_payload(payload)
        if not data:
            return
        judgment_items = data.get("Data", []) if isinstance(data, dict) else []
        if not judgment_items:
            return
        risk_signals = list(metadata.get("risk_signals", []))
        for item in judgment_items[:3]:
            case_name = item.get("CaseName") or item.get("CaseReason") or "裁判文书"
            case_type = item.get("CaseType")
            amount = item.get("Amount")
            parts = [str(case_name)]
            if case_type:
                parts.append(f"类型:{case_type}")
            if amount:
                parts.append(f"金额:{amount}")
            risk_signals.append("司法风险：" + "，".join(parts))
        metadata["risk_signals"] = _dedupe(risk_signals)

    def _merge_news_data(self, company_name: str, metadata: dict) -> None:
        payload = self.news_client.search_company_news(company_name)
        articles = payload.get("articles", [])
        if not articles:
            return
        risk_signals = list(metadata.get("risk_signals", []))
        source_notes = list(metadata.get("source_notes", []))
        for article in articles[:3]:
            title = article.get("title")
            published_at = article.get("publishedAt")
            source = (article.get("source") or {}).get("name")
            if title:
                risk_signals.append(
                    f"新闻舆情：{title}"
                    + (f"（{source}，{published_at}）" if source or published_at else "")
                )
        source_notes.append(f"NewsAPI articles: {len(articles)}")
        metadata["risk_signals"] = _dedupe(risk_signals)
        metadata["source_notes"] = _dedupe(source_notes)

    def _unwrap_payload(self, payload: dict[str, Any]) -> Any:
        if "Result" in payload:
            return payload["Result"]
        if "Data" in payload:
            return payload["Data"]
        return payload


def _dedupe(items: list[Any]) -> list[Any]:
    output: list[Any] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(item)
    return output
