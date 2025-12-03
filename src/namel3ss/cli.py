"""
Command-line interface for Namel3ss V3 (n3).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from . import ir, lexer, parser
from .server import create_app
from .runtime.engine import Engine


def load_module_from_file(path: Path):
    source = path.read_text(encoding="utf-8")
    tokens = lexer.Lexer(source, filename=str(path)).tokenize()
    return parser.Parser(tokens).parse_module()


def main(argv: list[str] | None = None) -> None:
    cli = argparse.ArgumentParser(prog="n3", description="Namel3ss V3 CLI")
    sub = cli.add_subparsers(dest="command", required=True)

    parse_cmd = sub.add_parser("parse", help="Parse an .ai file and show AST")
    parse_cmd.add_argument("file", type=Path)

    ir_cmd = sub.add_parser("ir", help="Generate IR from an .ai file")
    ir_cmd.add_argument("file", type=Path)

    run_cmd = sub.add_parser("run", help="Run an app from an .ai file")
    run_cmd.add_argument("app_name", type=str)
    run_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")

    graph_cmd = sub.add_parser("graph", help="Build reasoning graph for an .ai file")
    graph_cmd.add_argument("file", type=Path)

    serve_cmd = sub.add_parser("serve", help="Start the FastAPI server")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8000)
    serve_cmd.add_argument("--dry-run", action="store_true", help="Build app but do not start server")

    run_agent_cmd = sub.add_parser("run-agent", help="Run an agent from an .ai file")
    run_agent_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    run_agent_cmd.add_argument("--agent", required=True, help="Agent name to run")

    run_flow_cmd = sub.add_parser("run-flow", help="Run a flow from an .ai file")
    run_flow_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    run_flow_cmd.add_argument("--flow", required=True, help="Flow name to run")

    page_ui_cmd = sub.add_parser("page-ui", help="Render UI for a page")
    page_ui_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    page_ui_cmd.add_argument("--page", required=True, help="Page name to render")

    meta_cmd = sub.add_parser("meta", help="Show program metadata")
    meta_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")

    job_flow_cmd = sub.add_parser("job-flow", help="Enqueue a flow job")
    job_flow_cmd.add_argument("--file", type=Path, required=True)
    job_flow_cmd.add_argument("--flow", required=True)

    job_agent_cmd = sub.add_parser("job-agent", help="Enqueue an agent job")
    job_agent_cmd.add_argument("--file", type=Path, required=True)
    job_agent_cmd.add_argument("--agent", required=True)

    job_status_cmd = sub.add_parser("job-status", help="Check job status")
    job_status_cmd.add_argument("job_id")

    diag_cmd = sub.add_parser("diagnostics", help="Run diagnostics on an .ai file")
    diag_cmd.add_argument("--file", type=Path, required=True)
    diag_cmd.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    diag_cmd.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Diagnostics output format",
    )

    bundle_cmd = sub.add_parser("bundle", help="Create an app bundle")
    bundle_cmd.add_argument("--file", type=Path, required=True)
    bundle_cmd.add_argument("--target", choices=["server", "worker"], default="server")

    args = cli.parse_args(argv)

    if args.command == "parse":
        module = load_module_from_file(args.file)
        print(json.dumps(asdict(module), indent=2))
        return

    if args.command == "ir":
        module = load_module_from_file(args.file)
        program = ir.ast_to_ir(module)
        print(json.dumps(asdict(program), indent=2))
        return

    if args.command == "run":
        engine = Engine.from_file(args.file)
        result = engine.run_app(args.app_name)
        print(json.dumps(result, indent=2))
        return

    if args.command == "graph":
        engine = Engine.from_file(args.file)
        graph = engine.graph
        print(
            json.dumps(
                {
                    "nodes": [
                        {"id": node.id, "type": node.type, "label": node.label}
                        for node in graph.nodes.values()
                    ],
                    "edges": [
                        {"source": edge.source, "target": edge.target, "label": edge.label}
                        for edge in graph.edges
                    ],
                },
                indent=2,
            )
        )
        return

    if args.command == "serve":
        app = create_app()
        if args.dry_run:
            print(
                json.dumps(
                    {"status": "ready", "host": args.host, "port": args.port},
                    indent=2,
                )
            )
            return
        try:
            import uvicorn
        except ImportError as exc:  # pragma: no cover - runtime check
            raise SystemExit("uvicorn is required to run the server") from exc
        uvicorn.run(app, host=args.host, port=args.port)
        return

    if args.command == "run-agent":
        engine = Engine.from_file(args.file)
        result = engine.execute_agent(args.agent)
        print(json.dumps(result, indent=2))
        return

    if args.command == "run-flow":
        engine = Engine.from_file(args.file)
        result = engine.execute_flow(args.flow)
        print(json.dumps(result, indent=2))
        return

    if args.command == "page-ui":
        engine = Engine.from_file(args.file)
        if args.page not in engine.program.pages:
            raise SystemExit(f"Page '{args.page}' not found")
        ui_page = engine.ui_renderer.from_ir_page(engine.program.pages[args.page])
        print(f"Page: {ui_page.name} (route {ui_page.route})")
        for section in ui_page.sections:
            print(f"  [Section] {section.name}")
            for comp in section.components:
                props_str = ", ".join(f"{k}={v}" for k, v in comp.props.items())
                print(f"    - component {comp.type} ({props_str})")
        return

    if args.command == "meta":
        engine = Engine.from_file(args.file)
        meta = {
            "models": list(engine.registry.models.keys()),
            "providers": list(engine.registry.providers.keys()),
            "plugins": [p.name for p in engine.plugin_registry.list_plugins()],
            "flows": list(engine.program.flows.keys()),
            "pages": list(engine.program.pages.keys()),
        }
        print(json.dumps(meta, indent=2))
        return

    if args.command == "job-flow":
        from namel3ss.distributed.queue import global_job_queue
        from namel3ss.distributed.scheduler import JobScheduler

        scheduler = JobScheduler(global_job_queue)
        with open(args.file, "r", encoding="utf-8") as f:
            code = f.read()
        job = scheduler.schedule_flow(args.flow, {"code": code})
        print(json.dumps({"job_id": job.id}, indent=2))
        return

    if args.command == "job-agent":
        from namel3ss.distributed.queue import global_job_queue
        from namel3ss.distributed.scheduler import JobScheduler

        scheduler = JobScheduler(global_job_queue)
        with open(args.file, "r", encoding="utf-8") as f:
            code = f.read()
        job = scheduler.schedule_agent(args.agent, {"code": code})
        print(json.dumps({"job_id": job.id}, indent=2))
        return

    if args.command == "job-status":
        from namel3ss.distributed.queue import global_job_queue

        job = global_job_queue.get(args.job_id)
        print(json.dumps(job.__dict__ if job else {"error": "not found"}, indent=2))
        return

    if args.command == "diagnostics":
        from namel3ss.diagnostics.pipeline import run_diagnostics
        from namel3ss.diagnostics.models import has_effective_errors

        module = load_module_from_file(args.file)
        program = ir.ast_to_ir(module)
        diags = run_diagnostics(program, available_plugins=set())
        summary = {
            "error_count": sum(1 for d in diags if (d.severity or d.level) == "error"),
            "warning_count": sum(1 for d in diags if (d.severity or d.level) == "warning"),
            "strict": bool(args.strict),
        }
        if args.format == "json":
            payload = {
                "summary": summary,
                "diagnostics": [d.to_dict() for d in diags],
            }
            print(json.dumps(payload, indent=2))
        else:
            if not diags:
                print("No diagnostics found.")
            for diag in diags:
                loc = f" {diag.location}" if diag.location else ""
                hint = f" (hint: {diag.hint})" if diag.hint else ""
                print(f"[{diag.severity}][{diag.code}]{loc} - {diag.message}{hint}")
            print(f"Summary: errors={summary['error_count']} warnings={summary['warning_count']} strict={summary['strict']}")
        exit_code = 1 if has_effective_errors(diags, args.strict) else 0
        if exit_code != 0:
            raise SystemExit(exit_code)
        return

    if args.command == "bundle":
        from namel3ss.packaging.bundler import Bundler, make_server_bundle, make_worker_bundle

        module = load_module_from_file(args.file)
        program = ir.ast_to_ir(module)
        bundler = Bundler()
        bundle = bundler.from_ir(program)
        wrapped = make_worker_bundle(bundle) if args.target == "worker" else make_server_bundle(bundle)
        print(json.dumps(wrapped, indent=2))
        return


if __name__ == "__main__":  # pragma: no cover
    main()
