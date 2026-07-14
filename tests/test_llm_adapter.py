import json
from unittest import TestCase

from risk_himate.app.agents.domain_agents import DataComplianceAgent
from risk_himate.app.core.chunking import chunk_text
from risk_himate.app.core.schemas import TextChunk, TriageResult
from risk_himate.app.core.schemas import AnalysisInput
from risk_himate.app.llm.client import OpenAICompatibleLLMClient
from risk_himate.app.workflows.pipeline import RiskHiMATEPipeline


class StubLLMAdapterTests(TestCase):
    def test_pipeline_can_use_llm_adapter_for_triage_and_domain_agents(self) -> None:
        responses = [
            {
                "results": [
                    {
                        "chunk_id": "chunk-000",
                        "candidate_risk_types": ["数据合规风险"],
                        "relevance_score": 0.88,
                        "rationale": "命中跨境与用户数据。",
                    }
                ]
            },
            {
                "findings": [
                    {
                        "chunk_id": "chunk-000",
                        "category": "数据合规风险",
                        "subtype": "数据共享与出境",
                        "exists": True,
                        "severity": "high",
                        "confidence": 0.91,
                        "rationale": "数据共享与出境风险明显。",
                    }
                ]
            },
            {"findings": []},
            {"findings": []},
            {"findings": []},
            {"findings": []},
            {"issues": [], "summary": "无明显问题。", "overall_confidence": 0.9},
            {
                "revised_findings": {
                    "数据合规风险": [
                        {
                            "finding_id": "data_compliance-chunk-000",
                            "category": "数据合规风险",
                            "subtype": "数据共享与出境",
                            "exists": True,
                            "severity": "high",
                            "confidence": 0.91,
                            "evidence_chunk_ids": ["chunk-000"],
                            "rationale": "数据共享与出境风险明显。",
                            "revision_reason": "无须进一步修正。",
                        }
                    ]
                }
            },
            {
                "verdict": "accept",
                "confidence": 0.9,
                "accepted_finding_ids": [],
                "rejected_finding_ids": [],
                "needs_human_review": False,
                "notes": "通过",
            },
        ]

        def fake_post_json(url, headers, payload):
            return {"choices": [{"message": {"content": json.dumps(responses.pop(0), ensure_ascii=False)}}]}

        llm_client = OpenAICompatibleLLMClient(
            model="stub-model",
            api_key="stub-key",
            base_url="https://stub.local",
            post_json=fake_post_json,
        )
        pipeline = RiskHiMATEPipeline(llm_client=llm_client)
        result = pipeline.run(
            AnalysisInput(
                input_type="document",
                company_name="LLM样例科技",
                raw_text="企业计划将用户行为数据传输到境外云平台。",
            )
        )

        self.assertEqual(result["report"]["risk_details"][0]["subtype"], "数据共享与出境")
        self.assertEqual(result["debug"]["triage_results"][0]["relevance_score"], 0.88)

    def test_pipeline_falls_back_when_llm_adapter_raises(self) -> None:
        def failing_post_json(url, headers, payload):
            raise RuntimeError("network error")

        llm_client = OpenAICompatibleLLMClient(
            model="stub-model",
            api_key="stub-key",
            base_url="https://stub.local",
            post_json=failing_post_json,
        )
        pipeline = RiskHiMATEPipeline(llm_client=llm_client)
        result = pipeline.run(
            AnalysisInput(
                input_type="document",
                company_name="Fallback科技",
                raw_text="企业计划将用户个人信息传输到境外云平台，并面向海外客户提供服务。",
            )
        )

        self.assertTrue(result["report"]["risk_details"])

    def test_data_compliance_agent_llm_prompt_path_returns_high_severity_with_evidence(self) -> None:
        sample_text = "本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。"
        triage = TriageResult(
            chunk_id="chunk-000",
            text=sample_text,
            candidate_risk_types=["数据合规风险"],
            relevance_score=0.96,
            rationale="涉及面部识别、境外服务器、未告知用户。",
        )
        chunk = TextChunk(chunk_id="chunk-000", text=sample_text, source_type="document")

        def fake_post_json(url, headers, payload):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "findings": [
                                        {
                                            "chunk_id": "chunk-000",
                                            "category": "数据合规风险",
                                            "subtype": "数据共享与出境",
                                            "exists": True,
                                            "severity": "high",
                                            "confidence": 0.94,
                                            "rationale": "存在敏感个人信息处理、境外存储和未明确告知。",
                                        }
                                    ]
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

        llm_client = OpenAICompatibleLLMClient(
            model="stub-model",
            api_key="stub-key",
            base_url="https://stub.local",
            post_json=fake_post_json,
        )
        agent = DataComplianceAgent(llm_client=llm_client)
        findings = agent.analyze([triage], {"chunk-000": chunk})

        self.assertTrue(findings)
        self.assertEqual(findings[0].severity, "high")
        self.assertIn("境外服务器", findings[0].evidence)

    def test_pipeline_does_not_downgrade_high_llm_finding_during_rule_based_reflection(self) -> None:
        responses = [
            {
                "results": [
                    {
                        "chunk_id": "chunk-000",
                        "candidate_risk_types": ["数据合规风险"],
                        "relevance_score": 0.96,
                        "rationale": "涉及面部识别、境外服务器、未告知用户。",
                    }
                ]
            },
            {
                "findings": [
                    {
                        "chunk_id": "chunk-000",
                        "category": "数据合规风险",
                        "subtype": "数据采集合规",
                        "exists": True,
                        "severity": "high",
                        "confidence": 0.94,
                        "rationale": "存在敏感个人信息处理、境外存储和未明确告知。",
                    }
                ]
            },
            {"findings": []},
            {"findings": []},
            {"findings": []},
            {"findings": []},
        ]

        def fake_post_json(url, headers, payload):
            if responses:
                return {"choices": [{"message": {"content": json.dumps(responses.pop(0), ensure_ascii=False)}}]}
            raise RuntimeError("force fallback after domain-agent stage")

        llm_client = OpenAICompatibleLLMClient(
            model="stub-model",
            api_key="stub-key",
            base_url="https://stub.local",
            post_json=fake_post_json,
        )
        pipeline = RiskHiMATEPipeline(llm_client=llm_client)
        result = pipeline.run(
            AnalysisInput(
                input_type="document",
                company_name="高风险样例科技",
                raw_text="本公司收集用户面部识别数据用于广告推送，数据存储在境外服务器，未向用户明确告知。",
            )
        )

        detail = result["report"]["risk_details"][0]
        self.assertEqual(detail["category"], "数据合规风险")
        self.assertEqual(detail["severity"], "high")
