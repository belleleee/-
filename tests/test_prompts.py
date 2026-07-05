from pathlib import Path
from unittest import TestCase


PROMPT_DIR = Path(__file__).resolve().parent.parent / "risk_himate" / "app" / "llm" / "prompts"


class PromptStructureTests(TestCase):
    def test_domain_prompts_include_required_sections(self) -> None:
        domain_files = [
            "algorithm.md",
            "data_compliance.md",
            "ethics.md",
            "ip.md",
            "geopolitics.md",
        ]
        required_snippets = [
            "1. 角色定义",
            "2. 风险 taxonomy 定义",
            "3. 严重度判断标准",
            "4. 对应法规依据",
            "5. 输出规则",
            "6. 输出 JSON schema 示例",
            "evidence",
            "exists",
            "severity",
        ]
        for filename in domain_files:
            content = (PROMPT_DIR / filename).read_text(encoding="utf-8")
            for snippet in required_snippets:
                self.assertIn(snippet, content, f"{filename} missing section: {snippet}")

    def test_reflection_and_verifier_prompts_are_structured(self) -> None:
        reflection = (PROMPT_DIR / "reflection.md").read_text(encoding="utf-8")
        verifier = (PROMPT_DIR / "verifier.md").read_text(encoding="utf-8")

        self.assertIn("逐条指出问题", reflection)
        self.assertIn("missing_risk", reflection)
        self.assertIn("misclassified", reflection)
        self.assertIn("severity_issue", reflection)

        self.assertIn("accept", verifier)
        self.assertIn("partial_accept", verifier)
        self.assertIn("revert_to_original", verifier)
        self.assertIn("判断依据", verifier)
