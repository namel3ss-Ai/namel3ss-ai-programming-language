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
from .secrets.manager import SecretsManager


def build_cli_parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(prog="n3", description="Namel3ss V3 CLI")
    sub = cli.add_subparsers(dest="command", required=True)
    commands: list[str] = []

    def register(name: str, **kwargs):
        commands.append(name)
        return sub.add_parser(name, **kwargs)

    parse_cmd = register("parse", help="Parse an .ai file and show AST")
    parse_cmd.add_argument("file", type=Path)

    ir_cmd = register("ir", help="Generate IR from an .ai file")
    ir_cmd.add_argument("file", type=Path)

    run_cmd = register("run", help="Run an app from an .ai file")
    run_cmd.add_argument("app_name", type=str)
    run_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")

    graph_cmd = register("graph", help="Build reasoning graph for an .ai file")
    graph_cmd.add_argument("file", type=Path)

    serve_cmd = register("serve", help="Start the FastAPI server")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8000)
    serve_cmd.add_argument("--dry-run", action="store_true", help="Build app but do not start server")

    run_agent_cmd = register("run-agent", help="Run an agent from an .ai file")
    run_agent_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    run_agent_cmd.add_argument("--agent", required=True, help="Agent name to run")

    run_flow_cmd = register("run-flow", help="Run a flow from an .ai file")
    run_flow_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    run_flow_cmd.add_argument("--flow", required=True, help="Flow name to run")

    page_ui_cmd = register("page-ui", help="Render UI for a page")
    page_ui_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    page_ui_cmd.add_argument("--page", required=True, help="Page name to render")

    meta_cmd = register("meta", help="Show program metadata")
    meta_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")

    job_flow_cmd = register("job-flow", help="Enqueue a flow job")
    job_flow_cmd.add_argument("--file", type=Path, required=True)
    job_flow_cmd.add_argument("--flow", required=True)

    job_agent_cmd = register("job-agent", help="Enqueue an agent job")
    job_agent_cmd.add_argument("--file", type=Path, required=True)
    job_agent_cmd.add_argument("--agent", required=True)

    job_status_cmd = register("job-status", help="Check job status")
    job_status_cmd.add_argument("job_id")

    diag_cmd = register("diagnostics", help="Run diagnostics on an .ai file")
    diag_cmd.add_argument("--file", type=Path, required=True)
    diag_cmd.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    diag_cmd.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Diagnostics output format",
    )

    bundle_cmd = register("bundle", help="Create an app bundle")
    bundle_cmd.add_argument("--file", type=Path, required=True)
    bundle_cmd.add_argument("--target", choices=["server", "worker"], default="server")

    build_cmd = register("build-target", help="Build deployment target assets")
    build_cmd.add_argument("target", choices=["server", "worker", "docker", "serverless-aws", "desktop", "mobile"])
    build_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    build_cmd.add_argument("--output-dir", type=Path, required=True)

    optimize_cmd = register("optimize", help="Run optimizer actions")
    opt_sub = optimize_cmd.add_subparsers(dest="opt_command", required=True)
    opt_scan_cmd = opt_sub.add_parser("scan", help="Run optimizer scan once")
    opt_list_cmd = opt_sub.add_parser("list", help="List optimizer suggestions")
    opt_list_cmd.add_argument("--status", choices=["pending", "applied", "rejected", "expired"], default=None)
    opt_apply_cmd = opt_sub.add_parser("apply", help="Apply a suggestion by id")
    opt_apply_cmd.add_argument("suggestion_id")
    opt_reject_cmd = opt_sub.add_parser("reject", help="Reject a suggestion by id")
    opt_reject_cmd.add_argument("suggestion_id")
    opt_overlays_cmd = opt_sub.add_parser("overlays", help="Show optimizer overlays")
    opt_overlays_cmd.add_argument("--output", choices=["json", "text"], default="json")
    opt_overlays_cmd.set_defaults(output="json")

    cov_cmd = register("test-cov", help="Run tests with coverage")
    cov_cmd.add_argument("pytest_args", nargs="*", help="Additional pytest arguments")

    init_cmd = register("init", help="Scaffold a project from a template")
    init_cmd.add_argument("template", help="Template name")
    init_cmd.add_argument("target_dir", nargs="?", default=".", help="Target directory")
    init_cmd.add_argument("--force", action="store_true", help="Overwrite target directory if non-empty")

    cli._n3_commands = commands
    return cli


def load_module_from_file(path: Path):
    source = path.read_text(encoding="utf-8")
    tokens = lexer.Lexer(source, filename=str(path)).tokenize()
    return parser.Parser(tokens).parse_module()


def main(argv: list[str] | None = None) -> None:
    cli = build_cli_parser()
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

    if args.command == "build-target":
        from namel3ss.deploy.builder import DeployBuilder
        from namel3ss.deploy.models import DeployTargetConfig, DeployTargetKind

        source = args.file.read_text(encoding="utf-8")
        builder = DeployBuilder(source, args.output_dir)
        target_cfg = DeployTargetConfig(kind=DeployTargetKind(args.target), name=args.target, output_dir=args.output_dir)
        artifacts = builder.build([target_cfg])
        print(
            json.dumps(
                {"artifacts": [{"kind": str(a.kind), "path": str(a.path), "metadata": a.metadata} for a in artifacts]},
                indent=2,
            )
        )
        return

    if args.command == "optimize":
        from namel3ss.optimizer.engine import OptimizerEngine
        from namel3ss.optimizer.storage import OptimizerStorage
        from namel3ss.optimizer.overlays import OverlayStore
        from namel3ss.optimizer.apply import SuggestionApplier
        from namel3ss.metrics.tracker import MetricsTracker
        from namel3ss.obs.tracer import Tracer
        from namel3ss.optimizer.models import OptimizationStatus

        secrets = SecretsManager()
        storage = OptimizerStorage(Path(secrets.get("N3_OPTIMIZER_DB") or "optimizer.db"))
        overlays = OverlayStore(Path(secrets.get("N3_OPTIMIZER_OVERLAYS") or "optimizer_overlays.json"))
        if args.opt_command == "scan":
            engine = OptimizerEngine(
                storage=storage,
                metrics=MetricsTracker(),
                memory_engine=None,
                tracer=Tracer(),
                router=None,
                secrets=secrets,
            )
            suggestions = engine.scan()
            print(json.dumps({"created": [s.id for s in suggestions]}, indent=2))
            return
        if args.opt_command == "list":
            status = OptimizationStatus(args.status) if args.status else None
            payload = storage.list(status)
            print(json.dumps({"suggestions": [s.__dict__ for s in payload]}, indent=2))
            return
        if args.opt_command == "apply":
            sugg = storage.get(args.suggestion_id)
            if not sugg:
                raise SystemExit(f"Suggestion {args.suggestion_id} not found")
            applier = SuggestionApplier(overlays, storage, tracer=Tracer())
            applier.apply(sugg)
            print(json.dumps({"status": "applied"}, indent=2))
            return
        if args.opt_command == "reject":
            sugg = storage.get(args.suggestion_id)
            if not sugg:
                raise SystemExit(f"Suggestion {args.suggestion_id} not found")
            sugg.status = OptimizationStatus.REJECTED
            storage.update(sugg)
            print(json.dumps({"status": "rejected"}, indent=2))
            return
        if args.opt_command == "overlays":
            overlay = overlays.load().to_dict()
            if args.output == "json":
                print(json.dumps({"overlays": overlay}, indent=2))
            else:
                print(overlay)
            return

    if args.command == "test-cov":
        try:
            import pytest
        except ImportError as exc:  # pragma: no cover - runtime check
            raise SystemExit("pytest is required for coverage runs") from exc
        pytest_args = ["--cov=namel3ss", "--cov-report=term-missing"]
        pytest_args.extend(args.pytest_args or [])
        raise SystemExit(pytest.main(pytest_args))

    if args.command == "init":
        from namel3ss.templates import init_template, list_templates

        available = list_templates()
        if args.template not in available:
            raise SystemExit(f"Unknown template '{args.template}'. Available: {', '.join(available)}")
        dest = init_template(args.template, Path(args.target_dir), force=args.force)
        print(json.dumps({"status": "ok", "template": args.template, "path": str(dest)}, indent=2))
        return


if __name__ == "__main__":  # pragma: no cover
    main()
