"""CLI entrypoint for Risk-HiMATE."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from risk_himate.app.core.presentation import write_rendered_report
from risk_himate.app.core.schemas import AnalysisInput
from risk_himate.app.data_sources.company_profile_collector import LocalCompanyDataCollector
from risk_himate.app.data_sources.external_api_collector import ExternalCompanyDataCollector
from risk_himate.app.llm.client import OpenAICompatibleLLMClient
from risk_himate.app.storage.history_store import build_history_store
from risk_himate.app.workflows.pipeline import RiskHiMATEPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Risk-HiMATE")
    parser.add_argument("--text", help="Raw enterprise document text to analyze.")
    parser.add_argument("--company", help="Company name.")
    parser.add_argument(
        "--input-type",
        choices=["document", "company_name"],
        help="Explicitly choose the input type. Defaults to document when --text is present, else company_name.",
    )
    parser.add_argument(
        "--metadata-json",
        help="Optional JSON string merged into metadata for company_name collection.",
    )
    parser.add_argument(
        "--history-store",
        choices=["none", "json", "sqlite"],
        default="none",
        help="Persistence backend for historical reports.",
    )
    parser.add_argument(
        "--history-path",
        help="File path for the selected history store backend.",
    )
    parser.add_argument(
        "--collector",
        choices=["auto", "local", "external"],
        default="auto",
        help="Company-name data collector mode.",
    )
    parser.add_argument(
        "--company-data-path",
        help="Optional local company data JSON path for local fallback collector.",
    )
    parser.add_argument(
        "--llm-mode",
        choices=["auto", "rule", "llm"],
        default="auto",
        help="Use OpenAI-compatible LLM adapter or rule-based fallback.",
    )
    parser.add_argument(
        "--output",
        help="Optional output JSON file path. When omitted, results are printed to stdout only.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="When used with --output or stdout, emit only the report object instead of the full debug payload.",
    )
    parser.add_argument(
        "--rendered-report",
        help="Optional human-readable report output path. Supported extensions: .md, .html, .rtf, .docx",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    input_type = args.input_type or ("document" if args.text else "company_name")
    if input_type == "document" and not args.text:
        raise SystemExit("--text is required for document input.")
    if input_type == "company_name" and not args.company:
        raise SystemExit("--company is required for company_name input.")

    metadata = json.loads(args.metadata_json) if args.metadata_json else {}
    history_store = build_history_store(args.history_store, args.history_path)
    local_collector = LocalCompanyDataCollector(args.company_data_path) if args.company_data_path else LocalCompanyDataCollector()
    if args.collector == "local":
        company_collector = local_collector
    elif args.collector == "external":
        company_collector = ExternalCompanyDataCollector.from_env(fallback_collector=local_collector)
        if not company_collector.is_configured():
            raise SystemExit(
                "External collector selected but no API credentials found. "
                "Set QCC_APP_KEY/QCC_SECRET_KEY and/or NEWSAPI_KEY."
            )
    else:
        company_collector = ExternalCompanyDataCollector.from_env(fallback_collector=local_collector)

    llm_client = None
    if args.llm_mode != "rule":
        llm_client = OpenAICompatibleLLMClient.from_env()
    if args.llm_mode == "llm" and llm_client is None:
        raise SystemExit(
            "LLM mode selected but missing LLM_API_KEY/OPENAI_API_KEY or LLM_BASE_URL."
        )

    pipeline = RiskHiMATEPipeline(
        history_store=history_store,
        company_data_collector=company_collector,
        llm_client=llm_client,
    )
    analysis_input = AnalysisInput(
        input_type=input_type,
        company_name=args.company,
        raw_text=args.text,
        metadata=metadata,
    )
    state = pipeline.run_state(analysis_input)
    if state.risk_report is None:
        raise SystemExit("Risk report generation failed.")
    result = {
        "report": state.risk_report.model_dump(),
        "debug": {
            "input_type": state.analysis_input.input_type,
            "chunk_count": len(state.chunks),
            "triage_count": len(state.triage_results),
            "needs_human_review": state.needs_human_review,
            "triage_results": [result.model_dump() for result in state.triage_results],
            "reflection_result": state.reflection_result.model_dump() if state.reflection_result else None,
            "verification_result": state.verification_result.model_dump() if state.verification_result else None,
            "final_findings": [finding.model_dump() for finding in state.final_findings],
            "pipeline_state": state.model_dump(),
        },
    }
    output_payload = result["report"] if args.report_only else result
    output_text = json.dumps(output_payload, ensure_ascii=False, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")

    if args.rendered_report:
        rendered_output_path = Path(args.rendered_report)
        rendered_output_path.parent.mkdir(parents=True, exist_ok=True)
        write_rendered_report(state.risk_report, rendered_output_path)

    print(output_text)


if __name__ == "__main__":
    main()
