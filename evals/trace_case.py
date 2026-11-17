"""Single-file runner for eval traces."""
import argparse
import json
import os
import pathlib
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description="Run eval trace or dry-run.")
    parser.add_argument("--case", choices=["normal", "injection", "empty"], default="normal", help="Test case to run.")
    parser.add_argument("--dry-run", action="store_true", help="Build cases and print exact user turn without calling API.")
    args = parser.parse_args()

    root_dir = pathlib.Path(__file__).resolve().parent.parent
    fixtures_dir = root_dir / "fixtures"

    import docx
    from parsers.file_processor import FileProcessor
    from agent.audit_agent import AuditAgent

    def convert_fixtures_to_docx(case_dir: pathlib.Path, target_dir: pathlib.Path) -> list[str]:
        paths = []
        for md_path in sorted(case_dir.glob("*.md")):
            doc = docx.Document()
            for line in md_path.read_text(encoding="utf-8").splitlines():
                doc.add_paragraph(line)
            out_path = target_dir / f"{md_path.stem}.docx"
            doc.save(str(out_path))
            paths.append(str(out_path))
        return paths

    def build_case_content(case_name: str, target_dir: pathlib.Path) -> str:
        case_dir = fixtures_dir / f"case-{case_name}"
        docx_paths = convert_fixtures_to_docx(case_dir, target_dir)
        processor = FileProcessor()
        extracted = processor.process_files(docx_paths)
        agent = AuditAgent.__new__(AuditAgent)
        built = agent._build_content(extracted_files=extracted, lookback_years=5)
        return built[0]["text"]

    if args.dry_run:
        with tempfile.TemporaryDirectory() as td:
            temp_dir = pathlib.Path(td)
            for case_name in ("normal", "injection"):
                print(f"=== CASE: {case_name} ===")
                user_turn = build_case_content(case_name, temp_dir)
                print(user_turn)
                print()
        sys.exit(0)

    # Live run requires keys and OTel setup
    missing = [k for k in ("ORQ_API_KEY", "ANTHROPIC_API_KEY") if not os.environ.get(k)]
    if missing:
        sys.exit(f"Error: Missing required environment variable(s): {', '.join(missing)}")

    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    provider = TracerProvider(resource=Resource.create({"service.name": "finding-analysis"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
        endpoint="https://my.orq.ai/v2/otel/v1/traces",
        headers={"Authorization": f"Bearer {os.environ['ORQ_API_KEY']}"},
    )))
    trace.set_tracer_provider(provider)
    os.environ.setdefault("ANTHROPIC_OPEN_TELEMETRY_TRACES_CONTENT_MODE", "content")

    tracer = trace.get_tracer("finding-analysis")
    with tracer.start_as_current_span("analyze_findings") as span:
        span.set_attribute("gen_ai.agent.name", "finding-analysis")
        trace_id = format(span.get_span_context().trace_id, "032x")

        with tempfile.TemporaryDirectory() as td:
            temp_dir = pathlib.Path(td)
            case_dir = fixtures_dir / f"case-{args.case}"
            docx_paths = convert_fixtures_to_docx(case_dir, temp_dir)
            extracted = FileProcessor().process_files(docx_paths)
            agent = AuditAgent(api_key=os.environ["ANTHROPIC_API_KEY"])
            for _ in agent.analyze_stream(extracted, lookback_years=5):
                pass

        print(f"Trace ID: {trace_id}")


if __name__ == "__main__":
    main()
