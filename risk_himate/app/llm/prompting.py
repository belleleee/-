"""Prompt rendering helpers for Risk-HiMATE."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


def to_pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
