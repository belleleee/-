"""OpenAI-compatible LLM client and JSON helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any
from urllib.request import Request, urlopen


class LLMError(RuntimeError):
    """Raised when an LLM call fails or returns invalid content."""


def _default_post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        content = response.read().decode("utf-8")
    return json.loads(content)


@dataclass
class OpenAICompatibleLLMClient:
    model: str
    api_key: str
    base_url: str
    temperature: float = 0.0
    max_tokens: int = 1200
    post_json: Any = _default_post_json

    @classmethod
    def from_env(cls) -> "OpenAICompatibleLLMClient | None":
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("LLM_BASE_URL")
        model = os.getenv("LLM_MODEL", "qwen2.5-14b-instruct")
        if not api_key or not base_url:
            return None
        return cls(model=model, api_key=api_key, base_url=base_url.rstrip("/"))

    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        response = self.post_json(f"{self.base_url}/chat/completions", headers, payload)
        try:
            content = response["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Invalid LLM response payload: {response}") from exc
        return extract_json_object(content)


def extract_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{") or candidate.startswith("["):
                cleaned = candidate
                break
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMError(f"Could not locate JSON object in content: {content}")
    return json.loads(cleaned[start:end + 1])
