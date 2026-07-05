from unittest import TestCase

from risk_himate.app.data_sources.company_profile_collector import LocalCompanyDataCollector
from risk_himate.app.data_sources.external_api_collector import (
    ExternalCompanyDataCollector,
    NewsAPIClient,
    QCCOpenAPIClient,
)


class ExternalCollectorTests(TestCase):
    def test_qcc_client_adds_auth_headers(self) -> None:
        captured: dict = {}

        def fake_transport(url: str, headers: dict[str, str]) -> dict:
            captured["url"] = url
            captured["headers"] = headers
            return {"Result": {}}

        client = QCCOpenAPIClient(
            app_key="demo_key",
            secret_key="demo_secret",
            transport=fake_transport,
            base_url="https://api.example.com",
        )
        client.get_basic_details_by_name("示例科技")

        self.assertIn("/ECIV4/GetBasicDetailsByName", captured["url"])
        self.assertIn("key=demo_key", captured["url"])
        self.assertIn("keyword=%E7%A4%BA%E4%BE%8B%E7%A7%91%E6%8A%80", captured["url"])
        self.assertIn("Token", captured["headers"])
        self.assertIn("Timespan", captured["headers"])

    def test_external_collector_merges_qcc_and_news_payloads(self) -> None:
        qcc_basic = {
            "Result": {
                "Name": "示例科技",
                "Scope": "向海外客户提供智能推荐服务",
                "Address": "上海市浦东新区",
                "OperName": "张三",
                "Status": "存续",
                "EconKind": "人工智能服务",
                "CreditCode": "91310000123456789X",
                "TermEnd": "2036-01-01",
            }
        }
        qcc_patents = {
            "Result": [
                {"Title": "推荐引擎优化方法"},
                {"Title": "跨境数据治理平台"}
            ]
        }
        qcc_judgments = {
            "Result": {
                "Data": [
                    {"CaseName": "示例科技与某公司专利纠纷", "CaseType": "民事案件", "Amount": "100万"}
                ]
            }
        }
        news_payload = {
            "articles": [
                {
                    "title": "示例科技加速拓展海外市场",
                    "publishedAt": "2026-07-01T10:00:00Z",
                    "source": {"name": "TechNews"},
                }
            ]
        }

        basic_client = QCCOpenAPIClient("k", "s", transport=lambda *_: qcc_basic)
        patents_client = QCCOpenAPIClient("k", "s", transport=lambda *_: qcc_patents)
        judgments_client = QCCOpenAPIClient("k", "s", transport=lambda *_: qcc_judgments)

        class StubQCCClient:
            def get_basic_details_by_name(self, company_name: str) -> dict:
                return basic_client.get_basic_details_by_name(company_name)

            def get_patents(self, company_name: str, page_size: int = 10) -> dict:
                return patents_client.get_patents(company_name, page_size)

            def get_judgments(self, company_name: str, page_size: int = 10) -> dict:
                return judgments_client.get_judgments(company_name, page_size)

        news_client = NewsAPIClient("news", transport=lambda *_: news_payload)
        collector = ExternalCompanyDataCollector(
            qcc_client=StubQCCClient(),
            news_client=news_client,
            fallback_collector=LocalCompanyDataCollector(),
        )

        analysis_input = collector.collect("示例科技")

        self.assertEqual(analysis_input.metadata["collector_mode"], "external_api")
        self.assertIn("人工智能服务", analysis_input.metadata["sectors"])
        self.assertTrue(any("专利纠纷" in item for item in analysis_input.metadata["risk_signals"]))
        self.assertTrue(any("NewsAPI" in item for item in analysis_input.metadata["source_notes"]))
        self.assertIn("海外客户", analysis_input.raw_text)

    def test_external_collector_falls_back_to_local_when_unconfigured(self) -> None:
        collector = ExternalCompanyDataCollector(
            qcc_client=None,
            news_client=None,
            fallback_collector=LocalCompanyDataCollector(),
        )

        analysis_input = collector.collect("示例科技")

        self.assertEqual(analysis_input.metadata["collector_mode"], "fallback_local")
        self.assertIn("本地 mock 企业画像数据", "".join(analysis_input.metadata["source_notes"]))
