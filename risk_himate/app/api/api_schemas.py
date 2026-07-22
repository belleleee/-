"""API request/response schemas for Risk-HiMATE backend."""

from __future__ import annotations

from typing import Any, Literal

from risk_himate.app.core.compat import BaseModel, Field


class AnalyzeRequest(BaseModel):
    input_type: Literal["document", "company_name"]
    company_name: str | None = None
    raw_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    llm_mode: Literal["auto", "rule", "llm"] = "auto"
    report_only: bool = False


class ApiResponse(BaseModel):
    success: bool
    message: str = "ok"
    workflow_backend: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    success: bool
    message: str
    workflow_backend: str
    history_store: str
    collector_mode: str
    llm_available: bool

