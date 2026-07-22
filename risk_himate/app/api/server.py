"""FastAPI backend wrapper for Risk-HiMATE."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Any

from risk_himate.app.api.api_schemas import AnalyzeRequest, ApiResponse, HealthResponse
from risk_himate.app.core.schemas import AnalysisInput
from risk_himate.app.data_sources.company_profile_collector import LocalCompanyDataCollector
from risk_himate.app.data_sources.external_api_collector import ExternalCompanyDataCollector
from risk_himate.app.llm.client import OpenAICompatibleLLMClient
from risk_himate.app.storage.history_store import HistoryStore, build_history_store
from risk_himate.app.workflows.pipeline import RiskHiMATEPipeline


class ServerConfig:
    def __init__(self) -> None:
        self.history_store_kind = os.getenv("RISK_HIMATE_HISTORY_STORE", "none")
        self.history_path = os.getenv("RISK_HIMATE_HISTORY_PATH")
        self.collector_mode = os.getenv("RISK_HIMATE_COLLECTOR", "auto")
        self.company_data_path = os.getenv("RISK_HIMATE_COMPANY_DATA_PATH")

    def resolve_history_path(self) -> str | None:
        if self.history_path:
            return self.history_path
        if self.history_store_kind == "json":
            return str(Path("risk_himate/output/history_api.json"))
        if self.history_store_kind == "sqlite":
            return str(Path("risk_himate/output/history_api.sqlite3"))
        return None


CONFIG = ServerConfig()


def _build_collector():
    local_collector = (
        LocalCompanyDataCollector(CONFIG.company_data_path)
        if CONFIG.company_data_path
        else LocalCompanyDataCollector()
    )
    if CONFIG.collector_mode == "local":
        return local_collector
    if CONFIG.collector_mode == "external":
        collector = ExternalCompanyDataCollector.from_env(fallback_collector=local_collector)
        if not collector.is_configured():
            raise ValueError(
                "External collector selected but no API credentials found. "
                "Set QCC_APP_KEY/QCC_SECRET_KEY and/or NEWSAPI_KEY."
            )
        return collector
    return ExternalCompanyDataCollector.from_env(fallback_collector=local_collector)


@lru_cache(maxsize=4)
def _get_history_store() -> HistoryStore:
    return build_history_store(CONFIG.history_store_kind, CONFIG.resolve_history_path())


@lru_cache(maxsize=4)
def _get_pipeline(llm_mode: str) -> RiskHiMATEPipeline:
    llm_client = None
    if llm_mode != "rule":
        llm_client = OpenAICompatibleLLMClient.from_env()
    if llm_mode == "llm" and llm_client is None:
        raise ValueError("LLM mode selected but missing LLM_API_KEY/OPENAI_API_KEY or LLM_BASE_URL.")
    return RiskHiMATEPipeline(
        history_store=_get_history_store(),
        company_data_collector=_build_collector(),
        llm_client=llm_client,
    )


def _build_analysis_input(request: AnalyzeRequest) -> AnalysisInput:
    return AnalysisInput(
        input_type=request.input_type,
        company_name=request.company_name,
        raw_text=request.raw_text,
        metadata=request.metadata,
    )


def _report_payload(pipeline: RiskHiMATEPipeline, request: AnalyzeRequest) -> dict[str, Any]:
    result = pipeline.run(_build_analysis_input(request))
    if request.report_only:
        return {"report": result["report"]}
    return result


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app():
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "FastAPI backend dependencies are not installed. "
            "Install them with: python3 -m pip install fastapi uvicorn"
        ) from exc

    app = FastAPI(
        title="Risk-HiMATE API",
        version="0.1.0",
        description="LangGraph-native multi-agent risk analysis backend for sci-tech enterprises.",
    )

    if FRONTEND_DIR.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")

        @app.get("/", include_in_schema=False)
        def frontend_index():
            return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        try:
            pipeline = _get_pipeline("auto")
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return HealthResponse(
            success=True,
            message="ok",
            workflow_backend=pipeline.workflow_backend,
            history_store=CONFIG.history_store_kind,
            collector_mode=CONFIG.collector_mode,
            llm_available=OpenAICompatibleLLMClient.from_env() is not None,
        )

    @app.post("/analyze", response_model=ApiResponse)
    def analyze(request: AnalyzeRequest) -> ApiResponse:
        try:
            pipeline = _get_pipeline(request.llm_mode)
            data = _report_payload(pipeline, request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive backend boundary
            raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {exc}") from exc
        return ApiResponse(
            success=True,
            message="ok",
            workflow_backend=pipeline.workflow_backend,
            data=data,
        )

    @app.post("/analyze/report-only", response_model=ApiResponse)
    def analyze_report_only(request: AnalyzeRequest) -> ApiResponse:
        request.report_only = True
        return analyze(request)

    @app.get("/reports/{company}", response_model=ApiResponse)
    def get_latest_report(company: str) -> ApiResponse:
        history_store = _get_history_store()
        report = history_store.get_latest_report(company)
        if report is None:
            raise HTTPException(status_code=404, detail=f"No saved report found for company '{company}'.")
        return ApiResponse(
            success=True,
            message="ok",
            workflow_backend=None,
            data={"report": report.model_dump()},
        )

    return app


def main() -> None:
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "uvicorn is not installed. Install it with: python3 -m pip install uvicorn"
        ) from exc
    uvicorn.run(
        "risk_himate.app.api.server:create_app",
        factory=True,
        host=os.getenv("RISK_HIMATE_API_HOST", "127.0.0.1"),
        port=int(os.getenv("RISK_HIMATE_API_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
