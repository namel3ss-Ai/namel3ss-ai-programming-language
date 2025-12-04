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
from .diagnostics import Diagnostic
from .diagnostics.runner import apply_strict_mode, collect_diagnostics, iter_ai_files
from .lang.formatter import format_source
from .errors import ParseError
from .templates.manager import list_templates, scaffold_project
import sys


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

    diag_cmd = register("diagnostics", help="Run diagnostics on files or directories")
    diag_cmd.add_argument("paths", nargs="*", type=Path, help="Files or directories to analyze")
    diag_cmd.add_argument("--file", type=Path, help="Legacy single-file flag")
    diag_cmd.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    diag_cmd.add_argument("--json", action="store_true", help="Emit diagnostics as JSON")
    diag_cmd.add_argument("--summary-only", action="store_true", help="Only print the summary")

    bundle_cmd = register("bundle", help="Create an app bundle")
    bundle_cmd.add_argument("path", nargs="?", type=Path, help="Path to .ai file or project")
    bundle_cmd.add_argument("--file", type=Path, help="Legacy file flag (equivalent to positional path)")
    bundle_cmd.add_argument("--output", type=Path, default=Path("dist"), help="Output directory for bundle")
    bundle_cmd.add_argument("--name", type=str, help="Override bundle name")
    bundle_cmd.add_argument("--target", choices=["server", "full", "worker", "desktop"], default="server")
    bundle_cmd.add_argument("--env", action="append", default=[], help="Environment variable to include (KEY=VALUE)")
    bundle_cmd.add_argument("--dockerfile", action="store_true", help="Also generate Dockerfile for the bundle")

    desktop_cmd = register("desktop", help="Prepare a desktop (Tauri) bundle")
    desktop_cmd.add_argument("path", nargs="?", type=Path, help="Path to .ai file or project")
    desktop_cmd.add_argument("--file", type=Path, help="Legacy file flag")
    desktop_cmd.add_argument("--output", type=Path, default=Path("dist/desktop"), help="Output directory for desktop bundle")
    desktop_cmd.add_argument("--name", type=str, help="Override bundle name")
    desktop_cmd.add_argument("--env", action="append", default=[], help="Environment variable to include (KEY=VALUE)")
    desktop_cmd.add_argument("--dockerfile", action="store_true", help="Also generate Dockerfile for the bundle")
    desktop_cmd.add_argument("--no-build-tauri", action="store_true", help="Do not run tauri build (only prepare bundle)")

    mobile_cmd = register("mobile", help="Prepare mobile config (Expo)")
    mobile_cmd.add_argument("path", nargs="?", type=Path, help="Path to .ai file or project")
    mobile_cmd.add_argument("--file", type=Path, help="Legacy file flag")
    mobile_cmd.add_argument("--output", type=Path, default=Path("dist/mobile"), help="Output directory for mobile config")
    mobile_cmd.add_argument("--name", type=str, help="Override app name in config")
    mobile_cmd.add_argument("--no-expo-scaffold", action="store_true", help="Only emit config, do not scaffold Expo app")

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

    fmt_cmd = register("fmt", help="Format .ai files")
    fmt_cmd.add_argument("paths", nargs="*", type=Path, help="Files or directories to format")
    fmt_cmd.add_argument("--check", action="store_true", help="Only check formatting, do not write files")
    fmt_cmd.add_argument("--stdin", action="store_true", help="Read source from stdin and write to stdout")

    lsp_cmd = register("lsp", help="Start the Namel3ss language server (LSP) over stdio")

    create_cmd = register("create", help="Scaffold a new Namel3ss project from templates")
    create_cmd.add_argument("project_name", nargs="?", help="Name of the project / target directory")
    create_cmd.add_argument("--template", default="app-basic", help="Template name to use")
    create_cmd.add_argument("--force", action="store_true", help="Overwrite target directory if non-empty")
    create_cmd.add_argument("--list-templates", action="store_true", help="List available templates and exit")

    cli._n3_commands = commands
    return cli


def load_module_from_file(path: Path):
    source = path.read_text(encoding="utf-8")
    tokens = lexer.Lexer(source, filename=str(path)).tokenize()
    return parser.Parser(tokens).parse_module()


def _format_diagnostic(diag: Diagnostic) -> str:
    loc_parts = []
    if diag.file:
        loc_parts.append(str(diag.file))
    if diag.line is not None:
        loc_parts.append(str(diag.line))
    if diag.column is not None:
        loc_parts.append(str(diag.column))
    location = ":".join(loc_parts)
    prefix = f"{location} " if location else ""
    return f"{prefix}[{diag.severity}] ({diag.code} {diag.category}) {diag.message}"


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
        input_paths = list(args.paths)
        if args.file:
            input_paths.append(args.file)
        ai_files = iter_ai_files(input_paths)
        if not ai_files:
            print("No .ai files found.")
            return

        all_diags, summary = collect_diagnostics(ai_files, args.strict)
        success = summary["errors"] == 0

        if args.json:
            payload = {
                "success": success,
                "diagnostics": [] if args.summary_only else [d.to_dict() for d in all_diags],
                "summary": summary,
            }
            print(json.dumps(payload, indent=2))
        else:
            if not args.summary_only:
                if not all_diags:
                    print("No diagnostics found.")
                for diag in all_diags:
                    print(_format_diagnostic(diag))
                    if diag.hint:
                        print(f"  hint: {diag.hint}")
            print(f"Summary: {summary['errors']} errors, {summary['warnings']} warnings, {summary['infos']} infos across {len(ai_files)} files.")

        if not success:
            raise SystemExit(1)
        return

    if args.command == "fmt":
        if args.stdin:
            src = sys.stdin.read()
            try:
                formatted = format_source(src)
            except ParseError as err:
                print(f"stdin:{err.line}:{err.column}: parse error: {err.message}")
                raise SystemExit(1)
            if args.check:
                if formatted != src:
                    raise SystemExit(1)
                return
            sys.stdout.write(formatted)
            return

        input_paths = args.paths or [Path(".")]
        ai_files = iter_ai_files(input_paths)
        if not ai_files:
            print("No .ai files found.")
            return
        failed = False
        changed = False
        for path in ai_files:
            src = path.read_text(encoding="utf-8")
            try:
                formatted = format_source(src, filename=str(path))
            except ParseError as err:
                print(f"{path}:{err.line}:{err.column}: parse error: {err.message}")
                failed = True
                continue
            if args.check:
                if formatted != src:
                    print(f"{path} would be reformatted.")
                    changed = True
            else:
                if formatted != src:
                    path.write_text(formatted, encoding="utf-8")
        if failed or (args.check and changed):
            raise SystemExit(1)
        return

    if args.command == "lsp":
        from namel3ss.langserver import LanguageServer

        server = LanguageServer()
        server.run_stdio()
        return

    if args.command == "create":
        if args.list_templates:
            for name in list_templates():
                print(name)
            return
        if not args.project_name:
            raise SystemExit("project_name is required")
        target_dir = Path(args.project_name)
        template = args.template.replace("_", "-")
        try:
            scaffold_project(template, target_dir, project_name=target_dir.name, force=args.force)
        except FileExistsError as exc:
            print(str(exc))
            raise SystemExit(1)
        # Auto-format any .ai files in the new project
        for ai_file in target_dir.rglob("*.ai"):
            formatted = format_source(ai_file.read_text(encoding="utf-8"), filename=str(ai_file))
            ai_file.write_text(formatted, encoding="utf-8")
        print(f"Project created at {target_dir}")
        print("Next steps:")
        print(f"  cd {target_dir}")
        print("  n3 diagnostics .")
        return

    if args.command == "bundle":
        from namel3ss.packaging.bundler import Bundler
        from namel3ss.deploy.docker import generate_dockerfile
        from namel3ss.deploy.desktop import generate_tauri_config, write_tauri_config

        env_dict = {}
        for item in args.env or []:
            if "=" not in item:
                raise SystemExit(f"Invalid env value '{item}', expected KEY=VALUE")
            key, value = item.split("=", 1)
            env_dict[key] = value
        bundle_path = args.path or args.file
        if not bundle_path:
            raise SystemExit("A path to the app (.ai) is required")
        bundler = Bundler()
        try:
            bundle_root = bundler.build_bundle(
                bundle_path,
                target=args.target,
                output_dir=args.output,
                name=args.name,
                env=env_dict,
                include_studio=args.target == "full",
            )
        except Exception as exc:
            raise SystemExit(f"Failed to build bundle: {exc}") from exc
        manifest_path = bundle_root / "manifest.json"
        print(
            json.dumps(
                {"status": "ok", "bundle": str(bundle_root), "manifest": str(manifest_path), "type": args.target},
                indent=2,
            )
        )
        if args.dockerfile:
            from namel3ss.packaging.models import BundleManifest
            manifest = BundleManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))
            dockerfile = generate_dockerfile(manifest)
            (bundle_root / "Dockerfile").write_text(dockerfile, encoding="utf-8")
        if args.target == "desktop":
            from namel3ss.packaging.models import BundleManifest
            manifest = BundleManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))
            config = generate_tauri_config(manifest)
            write_tauri_config(config, bundle_root / "tauri.conf.json")
        return

    if args.command == "desktop":
        # Convenience wrapper for desktop bundles
        bundle_args = ["bundle"]
        if args.path:
            bundle_args.append(str(args.path))
        if args.file:
            bundle_args.extend(["--file", str(args.file)])
        bundle_args.extend(["--output", str(args.output)])
        bundle_args.extend(["--target", "desktop"])
        if args.name:
            bundle_args.extend(["--name", args.name])
        for env_item in args.env or []:
            bundle_args.extend(["--env", env_item])
        bundle_args.append("--dockerfile" if args.dockerfile else "")
        bundle_args = [arg for arg in bundle_args if arg]
        main(bundle_args)
        if not args.no_build_tauri:
            print(
                "Desktop bundle prepared. To build a native binary, install Tauri toolchain and run:\n"
                "  cd desktop && npm install && npm run tauri build"
            )
        return

    if args.command == "mobile":
        from namel3ss.deploy.mobile import generate_mobile_config, write_mobile_config
        from namel3ss.packaging.bundler import Bundler
        from namel3ss.packaging.models import BundleManifest

        bundle_path = args.path or args.file
        if not bundle_path:
            raise SystemExit("A path to the app (.ai) is required")
        out_dir = args.output
        out_dir.mkdir(parents=True, exist_ok=True)
        # Build a server bundle to derive manifest (no studio by default)
        bundler = Bundler()
        bundle_root = bundler.build_bundle(bundle_path, target="server", output_dir=out_dir, name=args.name)
        manifest_path = bundle_root / "manifest.json"
        manifest = BundleManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))
        config = generate_mobile_config(manifest)
        config_path = out_dir / "namel3ss.config.json"
        write_mobile_config(config, config_path)
        print(json.dumps({"status": "ok", "config": str(config_path), "bundle": str(bundle_root)}, indent=2))
        if not args.no_expo_scaffold:
            print(
                "Mobile config prepared. To run the Expo app, install Expo CLI and then:\n"
                "  cd mobile\n"
                "  npm install\n"
                "  npm start\n"
                "Configure the app to load namel3ss.config.json for the base URL."
            )
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
        available = list_templates()
        if args.template not in available:
            raise SystemExit(f"Unknown template '{args.template}'. Available: {', '.join(available)}")
        dest = Path(args.target_dir)
        try:
            scaffold_project(args.template, dest, project_name=dest.name, force=args.force)
        except FileExistsError as exc:
            print(str(exc))
            raise SystemExit(1)
        print(json.dumps({"status": "ok", "template": args.template, "path": str(dest)}, indent=2))
        return


if __name__ == "__main__":  # pragma: no cover
    main()
