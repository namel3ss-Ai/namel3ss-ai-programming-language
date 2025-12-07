"""
Command-line interface for Namel3ss (n3).
"""

from __future__ import annotations

import argparse
import contextlib
import http.server
import json
import multiprocessing
import socket
import sys
import threading
import time
import webbrowser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from dataclasses import asdict
from pathlib import Path

from . import ir, lexer, parser
from . import ast_nodes
from .server import create_app
from .runtime.engine import Engine
from .secrets.manager import SecretsManager
from .diagnostics import Diagnostic
from .diagnostics.runner import apply_strict_mode, collect_diagnostics, collect_lint, iter_ai_files
from .linting import LintConfig
from .lang.formatter import format_source
from .errors import ParseError
from .templates.manager import list_templates, scaffold_project
from .examples.manager import list_examples, resolve_example_path
from .version import __version__


def build_cli_parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(prog="n3", description="Namel3ss CLI")
    cli.add_argument(
        "--version",
        action="version",
        version=f"Namel3ss {__version__} (Python {sys.version.split()[0]})",
    )
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
    diag_cmd.add_argument("--lint", action="store_true", help="Include lint findings in the output")

    lint_cmd = register("lint", help="Run lint rules on files or directories")
    lint_cmd.add_argument("paths", nargs="*", type=Path, help="Files or directories to lint")
    lint_cmd.add_argument("--file", type=Path, help="Legacy single-file flag")
    lint_cmd.add_argument("--json", action="store_true", help="Emit lint results as JSON")

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
    build_cmd.add_argument(
        "target", choices=["server", "worker", "docker", "serverless-aws", "serverless-cloudflare", "desktop", "mobile"]
    )
    build_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    build_cmd.add_argument("--output-dir", type=Path, required=True)

    build_simple_cmd = register("build", help="Friendly build wrapper for common targets")
    build_simple_cmd.add_argument(
        "target",
        choices=["server", "worker", "docker", "serverless-aws", "serverless-cloudflare", "desktop", "mobile"],
        help="Target to build (desktop, mobile, serverless-aws, serverless-cloudflare, server, worker, docker)",
    )
    build_simple_cmd.add_argument("file", nargs="?", type=Path, help="Path to .ai file (optional)")
    build_simple_cmd.add_argument("--output-dir", type=Path, help="Override output directory")

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

    studio_cmd = register("studio", help="Start Namel3ss Studio (Phase 1)")
    studio_cmd.add_argument("--backend-port", type=int, default=8000, help="Port for backend runtime (default: 8000)")
    studio_cmd.add_argument("--ui-port", type=int, default=4173, help="Port for Studio UI (default: 4173)")
    studio_cmd.add_argument("--no-open-browser", action="store_true", help="Do not open a browser automatically")

    init_cmd = register("init", help="Scaffold a project from a template")
    init_cmd.add_argument("template", help="Template name")
    init_cmd.add_argument("target_dir", nargs="?", default=".", help="Target directory")
    init_cmd.add_argument("--force", action="store_true", help="Overwrite target directory if non-empty")

    example_cmd = register("example", help="Work with bundled examples")
    example_sub = example_cmd.add_subparsers(dest="example_command", required=True)
    example_sub.add_parser("list", help="List available examples")
    example_run_cmd = example_sub.add_parser("run", help="Run an example via /api/run-app")
    example_run_cmd.add_argument("name", help="Example name (folder and file name)")
    example_run_cmd.add_argument(
        "--api-base", default="http://localhost:8000", help="Base URL for the Namel3ss API"
    )

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


def _infer_app_name(source: str, filename: str, default: str) -> str:
    try:
        tokens = lexer.Lexer(source, filename=filename).tokenize()
        module = parser.Parser(tokens).parse_module()
        for decl in module.declarations:
            if isinstance(decl, ast_nodes.AppDecl):
                return decl.name
    except Exception:
        return default
    return default


def _post_run_app(source: str, app_name: str, api_base: str) -> dict:
    payload = json.dumps({"source": source, "app_name": app_name}).encode("utf-8")
    url = urljoin(api_base.rstrip("/") + "/", "api/run-app")
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(req) as resp:  # nosec - controlled by api_base
        return json.loads(resp.read().decode("utf-8"))


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
        lint_findings = []
        if args.lint:
            lint_findings = collect_lint(ai_files, config=LintConfig.load(Path.cwd()))
        success = summary["errors"] == 0

        if args.json:
            payload = {
                "success": success,
                "diagnostics": [] if args.summary_only else [d.to_dict() for d in all_diags],
                "lint": [] if args.summary_only else [d.to_dict() for d in lint_findings],
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
                for lint in lint_findings:
                    print(_format_diagnostic(lint))
            print(f"Summary: {summary['errors']} errors, {summary['warnings']} warnings, {summary['infos']} infos across {len(ai_files)} files.")

        if not success:
            raise SystemExit(1)
        return

    if args.command == "lint":
        input_paths = list(args.paths)
        if args.file:
            input_paths.append(args.file)
        ai_files = iter_ai_files(input_paths)
        if not ai_files:
            print("No .ai files found.")
            return
        lint_results = collect_lint(ai_files, config=LintConfig.load(Path.cwd()))
        error_count = sum(1 for d in lint_results if d.severity == "error")
        success = error_count == 0
        if args.json:
            print(
                json.dumps(
                    {
                        "success": success,
                        "lint": [d.to_dict() for d in lint_results],
                        "summary": {
                            "warnings": sum(1 for d in lint_results if d.severity == "warning"),
                            "infos": sum(1 for d in lint_results if d.severity == "info"),
                            "errors": error_count,
                        },
                    },
                    indent=2,
                )
            )
        else:
            if not lint_results:
                print("No lint findings.")
            for lint in lint_results:
                print(_format_diagnostic(lint))
            warn_count = sum(1 for d in lint_results if d.severity == "warning")
            info_count = sum(1 for d in lint_results if d.severity == "info")
            print(f"Summary: {error_count} errors, {warn_count} warnings, {info_count} infos across {len(ai_files)} files.")
        if not success:
            raise SystemExit(1)
        return

    if args.command == "example":
        if args.example_command == "list":
            for name in list_examples():
                print(name)
            return
        if args.example_command == "run":
            try:
                path = resolve_example_path(args.name)
            except FileNotFoundError as exc:
                raise SystemExit(str(exc)) from exc
            source = path.read_text(encoding="utf-8")
            app_name = _infer_app_name(source, str(path), args.name)
            try:
                raw_result = _post_run_app(source, app_name, args.api_base)
            except HTTPError as exc:
                detail = exc.read().decode("utf-8") if hasattr(exc, "read") else str(exc)
                raise SystemExit(f"Request failed ({exc.code}): {detail}") from exc
            except URLError as exc:
                raise SystemExit(f"Unable to reach API at {args.api_base}: {exc}") from exc
            result_block = raw_result.get("result") or {}
            trace = raw_result.get("trace") or result_block.get("trace")
            trace_id = trace.get("id") if isinstance(trace, dict) else None
            message = None
            if isinstance(result_block, dict):
                app_info = result_block.get("app")
                if isinstance(app_info, dict):
                    message = app_info.get("message")
            if not message:
                message = raw_result.get("message") or "Run completed"
            status = raw_result.get("status") or result_block.get("status") or "ok"
            payload = {"status": status, "message": message, "trace_id": trace_id}
            print(json.dumps(payload, indent=2))
            if trace_id:
                base = args.api_base.rstrip("/")
                print(f"\nOpen in Studio (trace):\n{base}/studio?trace={trace_id}")
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
    if args.command == "build":
        from namel3ss.deploy.builder import DeployBuilder
        from namel3ss.deploy.models import DeployTargetConfig, DeployTargetKind

        target = args.target

        def resolve_file() -> Path:
            if args.file:
                return args.file
            # prefer app.ai
            if Path("app.ai").exists():
                return Path("app.ai")
            ai_files = list(Path(".").glob("*.ai"))
            if len(ai_files) == 1:
                return ai_files[0]
            raise SystemExit(
                "No source file specified and no unique .ai file found. Please run: n3 build "
                f"{target} <file.ai>."
            )

        src_file = resolve_file()
        if not src_file.exists():
            raise SystemExit(f"Source file not found: {src_file}")
        out_dir = args.output_dir
        if out_dir is None:
            if target == "desktop":
                out_dir = Path("build/desktop")
            elif target == "mobile":
                out_dir = Path("build/mobile")
            else:
                out_dir = Path(f"build/{target}")
        out_dir.mkdir(parents=True, exist_ok=True)
        source = src_file.read_text(encoding="utf-8")
        builder = DeployBuilder(source, out_dir)
        target_cfg = DeployTargetConfig(kind=DeployTargetKind(target), name=target, output_dir=out_dir)
        artifacts = builder.build([target_cfg])
        print(f"Building {target} app from {src_file} -> {out_dir}")
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

    if args.command == "studio":
        run_studio(
            backend_port=args.backend_port,
            ui_port=args.ui_port,
            open_browser=not args.no_open_browser,
        )
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


# ----------------------------- Studio helpers ----------------------------- #
def detect_project_root(start: Path | None = None) -> Path | None:
    base = start or Path.cwd()
    if any(base.glob("*.ai")):
        return base
    return None


def _check_port_available(port: int, name: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"Port {port} is in use. Try: n3 studio --{name}-port <other>")


def start_backend_process(port: int) -> multiprocessing.Process:
    def target() -> None:
        import uvicorn
        from namel3ss.server import create_app

        app = create_app()
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

    proc = multiprocessing.Process(target=target, daemon=True)
    proc.start()
    return proc


class _StudioHandler(http.server.BaseHTTPRequestHandler):
    html = r"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Namel3ss Studio</title>
    <style>
      :root {
        color-scheme: dark;
        --bg: #0f172a;
        --bg-panel: #111827;
        --bg-muted: #0b1220;
        --border: #1f2937;
        --text: #e5e7eb;
        --muted: #9ca3af;
        --accent: #38bdf8;
        --accent-2: #8b5cf6;
        --danger: #f87171;
      }
      * { box-sizing: border-box; }
      body, html { margin: 0; padding: 0; width: 100%; height: 100%; background: var(--bg); color: var(--text); font-family: "Inter", "SF Pro Text", system-ui, -apple-system, sans-serif; }
      .studio-root { display: flex; flex-direction: column; height: 100vh; }
      .studio-topbar { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--bg-panel); border-bottom: 1px solid var(--border); }
      .logo { font-weight: 700; letter-spacing: 0.3px; }
      .nav-tabs { display: flex; gap: 12px; }
      .nav-tab { padding: 8px 12px; border-radius: 8px; color: var(--muted); cursor: pointer; transition: background 120ms ease, color 120ms ease; }
      .nav-tab.active { background: rgba(56,189,248,0.12); color: var(--text); border: 1px solid rgba(56,189,248,0.35); }
      .top-actions { display: flex; align-items: center; gap: 8px; }
      .btn { padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg-muted); color: var(--text); cursor: pointer; }
      .btn.primary { background: var(--accent); color: #0b1220; border-color: transparent; }
      .btn.ai { background: var(--accent-2); color: #f8fafc; border-color: transparent; }
      .studio-body { display: grid; grid-template-columns: 240px 1fr 260px; grid-template-rows: 1fr; flex: 1; min-height: 0; }
      .sidebar { background: var(--bg-panel); border-right: 1px solid var(--border); padding: 14px; overflow: auto; }
      .sidebar h3 { margin: 0 0 10px; font-size: 13px; letter-spacing: 0.6px; text-transform: uppercase; color: var(--muted); display:flex; align-items:center; justify-content: space-between; gap:8px; }
      .refresh-btn { background: var(--bg-muted); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 4px 6px; cursor: pointer; font-size: 12px; }
      .tree { font-family: "JetBrains Mono", "SFMono-Regular", Menlo, monospace; font-size: 13px; line-height: 1.6; color: var(--muted); }
      .tree .node { cursor: pointer; padding: 2px 4px; border-radius: 6px; display:flex; align-items:center; gap:6px; }
      .tree .node.active { background: rgba(56,189,248,0.12); color: var(--text); }
      .tree .folder { font-weight: 600; color: var(--text); }
      .tree .indent { display:inline-block; width: 14px; }
      .caret { width: 0; height: 0; border-top: 4px solid transparent; border-bottom: 4px solid transparent; border-left: 6px solid var(--muted); transition: transform 120ms ease; }
      .caret.open { transform: rotate(90deg); }
      .main { display: flex; flex-direction: column; background: var(--bg); }
      .main-tabs { display: flex; border-bottom: 1px solid var(--border); padding: 0 12px; background: var(--bg-panel); }
      .main-tab { padding: 10px 14px; cursor: pointer; color: var(--muted); border-bottom: 2px solid transparent; }
      .main-tab.active { color: var(--text); border-bottom-color: var(--accent); }
      .main-content { flex: 1; padding: 16px; overflow: auto; }
      .panel { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 10px; padding: 16px; min-height: 200px; }
      .panel h4 { margin-top: 0; }
      .editor-header { display:flex; justify-content: space-between; align-items:center; gap:12px; margin-bottom: 10px; }
      .file-label { font-family: "JetBrains Mono", "SFMono-Regular", Menlo, monospace; }
      .status-pill { padding: 6px 10px; border-radius: 999px; background: var(--bg-muted); border: 1px solid var(--border); font-size: 12px; color: var(--muted); }
      .monospace { font-family: "JetBrains Mono", "SFMono-Regular", Menlo, monospace; background: var(--bg-muted); padding: 12px; border-radius: 8px; border: 1px solid var(--border); }
      #code-editor { width: 100%; height: 60vh; resize: vertical; font-family: "JetBrains Mono", "SFMono-Regular", Menlo, monospace; font-size: 13px; line-height: 1.5; color: var(--text); background: var(--bg-muted); border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
      .rightbar { background: var(--bg-panel); border-left: 1px solid var(--border); padding: 14px; overflow: auto; }
      .rightbar h3 { margin: 0 0 10px; font-size: 13px; letter-spacing: 0.6px; text-transform: uppercase; color: var(--muted); }
      .section { margin-bottom: 14px; }
      .statusbar { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--bg-panel); border-top: 1px solid var(--border); font-size: 13px; color: var(--muted); }
      .status-items { display: flex; gap: 18px; align-items: center; }
      .tag { display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; border-radius: 6px; border: 1px solid var(--border); }
      .ui-controls { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
      .device-toggle { display: inline-flex; gap: 6px; }
      .device-btn { padding: 6px 10px; border: 1px solid var(--border); background: var(--bg-muted); color: var(--muted); border-radius: 8px; cursor: pointer; }
      .device-btn.active { color: var(--text); border-color: var(--accent); background: rgba(255,255,255,0.04); }
      #ui-preview-wrapper { display: flex; justify-content: center; padding: 16px; background: var(--bg-muted); border: 1px dashed var(--border); border-radius: 12px; min-height: 240px; }
      #ui-preview-frame { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 12px; padding: 18px; width: 100%; max-width: 1200px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
      .ui-section { display: flex; flex-direction: column; gap: 12px; margin-bottom: 10px; }
      .ui-heading { font-size: 22px; margin: 0; color: var(--text); }
      .ui-text { margin: 0; color: var(--muted); }
      .ui-input { display: flex; flex-direction: column; gap: 6px; }
      .ui-input input { padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg-muted); color: var(--text); }
      .ui-button { padding: 10px 14px; border-radius: 8px; border: 1px solid var(--border); background: var(--accent); color: #fff; cursor: pointer; }
      .ui-img { max-width: 100%; border-radius: 10px; border: 1px solid var(--border); }
      .ui-hover { outline: 1px dashed transparent; }
      .ui-hover:hover { outline-color: var(--accent); }
      .ui-selected { outline: 2px solid var(--accent-2) !important; outline-offset: 2px; }
      .mode-toggle { display: inline-flex; gap: 8px; }
      .mode-btn { padding: 6px 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg-muted); color: var(--muted); cursor: pointer; }
      .mode-btn.active { color: var(--text); border-color: var(--accent); background: rgba(255,255,255,0.04); }
      .inspector-section { margin-bottom: 14px; }
      .inspector-section h4 { margin: 0 0 6px; font-size: 13px; color: var(--muted); letter-spacing: 0.5px; text-transform: uppercase; }
      .inspector-item { margin: 2px 0; font-size: 13px; }
      .route-display { font-size: 13px; color: var(--muted); }
    </style>
  </head>
  <body>
    <div class="studio-root">
      <header class="studio-topbar">
        <div class="logo">Namel3ss Studio</div>
        <div class="nav-tabs" id="nav-tabs">
          <div class="nav-tab active" data-nav="Pages">Pages</div>
          <div class="nav-tab" data-nav="Flows">Flows</div>
          <div class="nav-tab" data-nav="Agents">Agents</div>
          <div class="nav-tab" data-nav="UI">UI</div>
          <div class="nav-tab" data-nav="Data">Data</div>
        </div>
        <div class="top-actions">
          <button class="btn primary">Run</button>
          <button class="btn ai">✨ AI</button>
          <button class="btn">Settings</button>
        </div>
      </header>

      <div class="studio-body">
        <aside class="sidebar">
          <h3>Project <button class="refresh-btn" id="project-refresh">↻</button></h3>
          <div class="tree" id="project-tree"></div>
          <div id="tree-empty" style="color: var(--muted); font-size: 13px; display:none;">No .ai files found.</div>
        </aside>

        <main class="main">
          <div class="main-tabs" id="main-tabs">
            <div class="main-tab active" data-tab="code">Code</div>
            <div class="main-tab" data-tab="ui">UI</div>
            <div class="main-tab" data-tab="graph">Flow Graph</div>
          </div>
          <div class="main-content">
            <div class="panel" id="content-code">
              <div class="editor-header">
                <div class="file-label" id="editing-label">No file selected</div>
                <div class="status-pill" id="save-status">Idle</div>
              </div>
              <textarea id="code-editor" spellcheck="false" placeholder="Select a file in the Project sidebar to start editing."></textarea>
            </div>
            <div class="panel" id="content-ui" style="display:none;">
              <div class="ui-controls">
                <div class="device-toggle">
                  <button class="device-btn active" data-device="desktop" id="device-desktop">Desktop</button>
                  <button class="device-btn" data-device="tablet" id="device-tablet">Tablet</button>
                  <button class="device-btn" data-device="phone" id="device-phone">Phone</button>
                </div>
                <div class="mode-toggle">
                  <button class="mode-btn active" data-mode="preview" id="mode-preview">Preview Mode</button>
                  <button class="mode-btn" data-mode="inspect" id="mode-inspect">Inspector Mode</button>
                </div>
                <div style="display:flex; gap:8px; align-items:center;">
                  <button class="btn" id="ui-back">◀ Back</button>
                  <button class="btn" id="ui-forward">▶ Forward</button>
                  <span class="route-display" id="route-label">Route: /</span>
                  <span id="ui-preview-status" style="color: var(--muted); font-size: 13px;">Loading preview…</span>
                  <button class="btn" id="ui-refresh">↻ Refresh preview</button>
                </div>
              </div>
              <div id="ui-preview-wrapper">
                <div id="ui-preview-frame">
                  <div id="ui-preview">Loading UI preview…</div>
                </div>
              </div>
              <div class="monospace" id="ui-console" style="margin-top:12px; white-space:pre-wrap;">No actions run yet.</div>
            </div>
            <div class="panel" id="content-graph" style="display:none;">
              <h4>Flow Graph</h4>
              <p>Flow graph will appear here in Studio Phase 5.</p>
            </div>
          </div>
        </main>

      <aside class="rightbar">
        <h3>Inspector</h3>
          <div id="palette" class="section" style="margin-bottom:12px;">
            <strong>Palette</strong>
            <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:6px;">
              <button class="btn" data-new="heading" onclick="insertFromPalette('heading')">Heading</button>
              <button class="btn" data-new="text" onclick="insertFromPalette('text')">Text</button>
              <button class="btn" data-new="button" onclick="insertFromPalette('button')">Button</button>
              <button class="btn" data-new="input" onclick="insertFromPalette('input')">Input</button>
              <button class="btn" data-new="section" onclick="insertFromPalette('section')">Section</button>
              <button class="btn" id="ai-generate-btn" onclick="openAIModal()">⚡ AI Generate UI</button>
            </div>
          </div>
          <div id="ai-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:9999; align-items:center; justify-content:center;">
            <div style="background:#111; color:#f5f5f5; padding:16px; width:480px; max-width:90%; border:1px solid #333; border-radius:8px;">
              <h3 style="margin-top:0;">Generate UI with AI</h3>
              <p style="font-size:13px; color:#ccc;">Describe the layout you want. The AI will insert UI code into the current page.</p>
              <textarea id="ai-prompt" style="width:100%; min-height:120px; background:#0c0c0c; color:#fff; border:1px solid #333; padding:8px; border-radius:4px;"></textarea>
              <div style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">
                <button class="btn" onclick="fillPrompt('Create a login form with email and password, centered, with a primary button.')">Login form</button>
                <button class="btn" onclick="fillPrompt('Two column hero with heading on left and signup form on right.')">Hero + form</button>
              </div>
              <div style="margin-top:12px; display:flex; justify-content:flex-end; gap:8px;">
                <button class="btn" onclick="closeAIModal()">Cancel</button>
                <button class="btn" onclick="submitAIGenerate()">Generate</button>
              </div>
            </div>
          </div>
          <div id="inspector-body"></div>
      </aside>
      </div>

      <footer class="statusbar">
        <div class="status-items">
          <span class="tag">Backend: Connected</span>
          <span class="tag">Last run: N/A</span>
          <span class="tag">Diagnostics: Errors 0 · Warnings 0</span>
        </div>
        <div class="status-items">
          <span class="tag">Theme: Dark</span>
        </div>
      </footer>
    </div>

    <script>
      const API_KEY = "dev-key";
      let treeData = null;
      let currentFile = null;
      let dirty = false;
      let saveTimer = null;
      let uiManifest = null;
      let deviceMode = "desktop";
      let previewLoading = false;
      let previewState = {};
      let lastAction = null;
      let flowRunning = false;
      let elementIndex = {};
      let selectedElementId = null;
      let previewMode = "preview";
      let routeHistory = [];
      let forwardStack = [];
      let currentRoute = null;
      let pageRegistry = {};

      const editorEl = document.getElementById('code-editor');
      const fileLabel = document.getElementById('editing-label');
      const saveStatus = document.getElementById('save-status');
      const treeContainer = document.getElementById('project-tree');
      const treeEmpty = document.getElementById('tree-empty');
      const refreshBtn = document.getElementById('project-refresh');
      const uiPreview = document.getElementById('ui-preview');
      const uiPreviewStatus = document.getElementById('ui-preview-status');
      const uiPreviewFrame = document.getElementById('ui-preview-frame');
      const uiRefreshBtn = document.getElementById('ui-refresh');
      const deviceButtons = Array.from(document.querySelectorAll('.device-btn'));
      const modeButtons = Array.from(document.querySelectorAll('.mode-btn'));
      const backBtn = document.getElementById('ui-back');
      const fwdBtn = document.getElementById('ui-forward');
      const routeLabel = document.getElementById('route-label');
      const aiModal = document.getElementById('ai-modal');
      const aiPrompt = document.getElementById('ai-prompt');

      function setStatus(text, tone="muted") {
        saveStatus.textContent = text;
        if (tone === "ok") {
          saveStatus.style.color = "#34d399";
        } else if (tone === "error") {
          saveStatus.style.color = "#f87171";
        } else if (tone === "busy") {
          saveStatus.style.color = "#fbbf24";
        } else {
          saveStatus.style.color = "var(--muted)";
        }
      }

      function setPreviewStatus(text) {
        if (uiPreviewStatus) uiPreviewStatus.textContent = text;
      }

      function resolveColor(value, theme) {
        if (!value) return undefined;
        if (theme && theme[value]) return theme[value];
        return value;
      }

      function applyStyles(el, styles, theme) {
        const map = {};
        (styles || []).forEach((s) => { map[s.kind] = s.value; });
        if (map.color) el.style.color = resolveColor(map.color, theme);
        if (map.bg_color || map.background_color) el.style.backgroundColor = resolveColor(map.bg_color || map.background_color, theme);
        if (map.align) el.style.textAlign = map.align;
        if (map.align_h) el.style.textAlign = map.align_h;
        const spacing = { small: 8, medium: 16, large: 24 };
        if (map.padding && spacing[map.padding]) el.style.padding = `${spacing[map.padding]}px`;
        if (map.margin && spacing[map.margin]) el.style.margin = `${spacing[map.margin]}px`;
        if (map.gap && spacing[map.gap]) el.style.gap = `${spacing[map.gap]}px`;
        if (map.layout) {
          if (map.layout === "row") {
            el.style.display = "flex";
            el.style.flexDirection = "row";
            el.style.gap = el.style.gap || "12px";
          } else if (map.layout === "column") {
            el.style.display = "flex";
            el.style.flexDirection = "column";
            el.style.gap = el.style.gap || "12px";
          } else if (map.layout === "two_columns") {
            el.style.display = "grid";
            el.style.gridTemplateColumns = "repeat(2, minmax(0, 1fr))";
            el.style.gap = el.style.gap || "12px";
          } else if (map.layout === "three_columns") {
            el.style.display = "grid";
            el.style.gridTemplateColumns = "repeat(3, minmax(0, 1fr))";
            el.style.gap = el.style.gap || "12px";
          }
        }
        if (map.valign || map.align_v) {
          el.style.display = el.style.display || "flex";
          const val = map.valign || map.align_v;
          el.style.alignItems = val === "middle" ? "center" : val;
        }
      }

      function renderLayout(node, theme, pageName) {
        if (!node) return document.createElement('div');
        const type = node.type;
        if (type === "section") {
          const el = document.createElement('div');
          el.className = "ui-section";
          applyStyles(el, node.styles, theme);
          (node.layout || []).forEach(child => el.appendChild(renderLayout(child, theme, pageName)));
          return wrapInspectable(node, el, pageName);
        }
        if (type === "heading") {
          const el = document.createElement('h2');
          el.className = "ui-heading";
          el.textContent = node.text || "";
          applyStyles(el, node.styles, theme);
          return wrapInspectable(node, el, pageName);
        }
        if (type === "text") {
          const el = document.createElement('p');
          el.className = "ui-text";
          el.textContent = node.text || "";
          applyStyles(el, node.styles, theme);
          return wrapInspectable(node, el, pageName);
        }
        if (type === "image") {
          const el = document.createElement('img');
          el.className = "ui-img";
          el.src = node.url || "";
          applyStyles(el, node.styles, theme);
          return el;
        }
        if (type === "card") {
          const wrap = document.createElement('div');
          wrap.className = "ui-card";
          wrap.style.border = "1px solid #e5e7eb";
          wrap.style.borderRadius = "12px";
          wrap.style.padding = "16px";
          wrap.style.background = "#fff";
          wrap.style.boxShadow = "0 4px 14px rgba(0,0,0,0.04)";
          if (node.title) {
            const title = document.createElement('div');
            title.style.fontWeight = "600";
            title.style.marginBottom = "8px";
            title.textContent = node.title;
            wrap.appendChild(title);
          }
          applyStyles(wrap, node.styles, theme);
          (node.layout || []).forEach(child => wrap.appendChild(renderLayout(child, theme, pageName)));
          return wrapInspectable(node, wrap, pageName);
        }
        if (type === "row") {
          const wrap = document.createElement('div');
          wrap.className = "ui-row";
          wrap.style.display = "flex";
          wrap.style.gap = "12px";
          applyStyles(wrap, node.styles, theme);
          (node.layout || []).forEach(child => wrap.appendChild(renderLayout(child, theme, pageName)));
          return wrapInspectable(node, wrap, pageName);
        }
        if (type === "column") {
          const wrap = document.createElement('div');
          wrap.className = "ui-column";
          wrap.style.display = "flex";
          wrap.style.flexDirection = "column";
          wrap.style.gap = "12px";
          applyStyles(wrap, node.styles, theme);
          (node.layout || []).forEach(child => wrap.appendChild(renderLayout(child, theme, pageName)));
          return wrapInspectable(node, wrap, pageName);
        }
        if (type === "input") {
          const wrap = document.createElement('div');
          wrap.className = "ui-input";
          const label = document.createElement('label');
          label.textContent = node.label || node.name || "Input";
          const input = document.createElement('input');
          input.type = node.field_type || "text";
          const key = node.name || node.label || Math.random().toString(36).slice(2);
          if (!(key in previewState)) previewState[key] = "";
          input.value = previewState[key];
          input.addEventListener('input', (e) => {
            previewState[key] = e.target.value;
          });
          applyStyles(wrap, node.styles, theme);
          wrap.appendChild(label);
          wrap.appendChild(input);
          return wrap;
        }
        if (type === "textarea") {
          const wrap = document.createElement('div');
          wrap.className = "ui-textarea";
          const label = document.createElement('label');
          label.textContent = node.label || node.name || "Textarea";
          const textarea = document.createElement('textarea');
          textarea.rows = 4;
          const key = node.name || node.label || Math.random().toString(36).slice(2);
          if (!(key in previewState)) previewState[key] = "";
          textarea.value = previewState[key];
          textarea.addEventListener('input', (e) => {
            previewState[key] = e.target.value;
          });
          applyStyles(wrap, node.styles, theme);
          wrap.appendChild(label);
          wrap.appendChild(textarea);
          return wrap;
        }
        if (type === "badge") {
          const el = document.createElement('span');
          el.className = "ui-badge";
          el.textContent = node.text || "";
          el.style.display = "inline-flex";
          el.style.alignItems = "center";
          el.style.padding = "4px 8px";
          el.style.borderRadius = "999px";
          el.style.background = "#f1f5f9";
          el.style.fontSize = "12px";
          el.style.fontWeight = "600";
          applyStyles(el, node.styles, theme);
          return wrapInspectable(node, el, pageName);
        }
        if (type === "button") {
          const el = document.createElement('button');
          el.className = "ui-button";
          el.textContent = node.label || "Button";
          applyStyles(el, node.styles, theme);
          if (node.actions && node.actions.length > 0) {
            const flowAction = node.actions.find(a => a.kind === "flow");
            const navAction = node.actions.find(a => a.kind === "goto_page");
            el.style.cursor = "pointer";
            el.addEventListener('click', async () => {
              if (previewMode === "inspect") {
                setSelected(node.id, pageName);
                return;
              }
              if (navAction) {
                const targetRoute = navAction.route || `/${navAction.target}`;
                setRoute(targetRoute, true);
                return;
              }
              if (flowAction) {
                if (flowRunning) return;
                flowRunning = true;
                el.disabled = true;
                const orig = el.textContent;
                el.textContent = "Running…";
                const args = {};
                Object.entries(flowAction.args || {}).forEach(([k, v]) => {
                  if (v && v.identifier) {
                    args[k] = previewState[v.identifier] ?? "";
                  } else if (v && v.literal !== undefined) {
                    args[k] = v.literal;
                  }
                });
                const payload = { flow: flowAction.target, args };
                try {
                  const res = await fetch('/api/ui/flow/execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', "X-API-Key": API_KEY },
                    body: JSON.stringify(payload)
                  });
                  const data = await res.json();
                  lastAction = { flow: flowAction.target, payload: args, response: data };
                  renderConsole();
                } catch (err) {
                  lastAction = { flow: flowAction.target, payload: args, response: { success: false, error: String(err) } };
                  renderConsole();
                } finally {
                  flowRunning = false;
                  el.disabled = false;
                  el.textContent = orig;
                }
              }
            });
          }
          return el;
        }
        if (type === "conditional") {
          const wrap = document.createElement('div');
          applyStyles(wrap, node.styles, theme);
          (node.when || []).forEach(child => wrap.appendChild(renderLayout(child, theme, pageName)));
          return wrapInspectable(node, wrap, pageName);
        }
        return document.createElement('div');
      }

      function getPageByRoute(route) {
        if (!route || !uiManifest || !uiManifest.pages) return null;
        return uiManifest.pages.find((p) => p.route === route) || null;
      }

      function resolvePageForSelection() {
        if (!uiManifest || !uiManifest.pages || uiManifest.pages.length === 0) return null;
        if (currentRoute) {
          const byRoute = getPageByRoute(currentRoute);
          if (byRoute) return byRoute;
        }
        if (currentFile && currentFile.includes("pages/")) {
          const stem = currentFile.split("/").pop().replace(/\\.ai$/i, "");
          const byPath = uiManifest.pages.find((p) => p.source_path === currentFile);
          if (byPath) return byPath;
          const byName = uiManifest.pages.find((p) => (p.name || "").toLowerCase() === stem.toLowerCase());
          if (byName) return byName;
        }
        return uiManifest.pages[0];
      }

      function setRoute(route, push=true) {
        if (!route) return;
        const page = getPageByRoute(route);
        if (!page) return;
        if (push && currentRoute) {
          routeHistory.push(currentRoute);
          forwardStack = [];
        }
        currentRoute = route;
        if (routeLabel) routeLabel.textContent = `Route: ${route}`;
        renderPreview();
        if (backBtn) backBtn.disabled = routeHistory.length === 0;
        if (fwdBtn) fwdBtn.disabled = forwardStack.length === 0;
      }

      function renderPreview() {
        if (!uiPreview) return;
        const widths = { desktop: 1200, tablet: 800, phone: 420 };
        uiPreview.innerHTML = "";
        if (uiPreviewFrame) uiPreviewFrame.style.maxWidth = `${widths[deviceMode] || widths.desktop}px`;
        if (previewLoading) {
          uiPreview.textContent = "Loading UI preview…";
          return;
        }
        if (!uiManifest || !uiManifest.pages || uiManifest.pages.length === 0) {
          uiPreview.textContent = "No UI pages found. Define a 'page' in your .ai files to see a preview.";
          return;
        }
        const page = resolvePageForSelection();
        if (!page) {
          uiPreview.textContent = "Select a page file in the Project sidebar to preview it.";
          return;
        }
        if (!currentRoute) currentRoute = page.route;
        if (routeLabel && currentRoute) routeLabel.textContent = `Route: ${currentRoute}`;
        previewState = {};
        elementIndex = {};
        const theme = uiManifest.theme || {};
        const container = document.createElement('div');
        applyStyles(container, page.styles, theme);
        (page.layout || []).forEach(child => container.appendChild(renderLayout(child, theme, page.name)));
        uiPreview.appendChild(container);
        setPreviewStatus(`Showing: ${page.name || "page"}`);
        renderInspector();
      }

      function renderConsole() {
        const consoleEl = document.getElementById('ui-console');
        if (!consoleEl) return;
        if (!lastAction) {
          consoleEl.textContent = "No actions run yet.";
          return;
        }
        const { flow, payload, response } = lastAction;
        const lines = [];
        lines.push(`Flow: ${flow}`);
        lines.push(`Status: ${response && response.success ? "success" : "failed"}`);
        if (payload) lines.push(`Args: ${JSON.stringify(payload, null, 2)}`);
        if (response && response.result) lines.push(`Result: ${JSON.stringify(response.result, null, 2)}`);
        if (response && response.error) lines.push(`Error: ${response.error}`);
        if (response && response.diagnostics) lines.push(`Diagnostics: ${JSON.stringify(response.diagnostics)}`);
        consoleEl.textContent = lines.join("\n");
      }

      async function performTransform(body) {
        try {
          const res = await fetch('/api/studio/code/transform', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', "X-API-Key": API_KEY },
            body: JSON.stringify(body),
          });
          const data = await res.json();
          if (!res.ok || !data.success) {
            alert(`Transform failed: ${data.detail || data.error || res.statusText}`);
            return null;
          }
          if (data.manifest) {
            uiManifest = data.manifest;
            if (data.new_element_id) selectedElementId = data.new_element_id;
            renderPreview();
          }
          if (currentFile && currentFile === body.path) {
            selectFile(currentFile);
          }
          return data;
        } catch (err) {
          alert(`Transform error: ${err}`);
          return null;
        }
      }

      function openAIModal() {
        if (previewMode !== "inspect") return;
        if (aiModal) aiModal.style.display = "flex";
        if (aiPrompt) aiPrompt.focus();
      }

      function closeAIModal() {
        if (aiModal) aiModal.style.display = "none";
      }

      function fillPrompt(text) {
        if (aiPrompt) aiPrompt.value = text;
      }

      async function submitAIGenerate() {
        if (!aiPrompt) return;
        const prompt = aiPrompt.value.trim();
        if (!prompt) {
          alert("Enter a prompt to generate UI.");
          return;
        }
        if (!currentFile) {
          alert("Open a page file first.");
          return;
        }
        try {
          const res = await fetch('/api/studio/ui/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', "X-API-Key": API_KEY },
            body: JSON.stringify({
              prompt,
              page_path: currentFile,
              selected_element_id: selectedElementId,
            }),
          });
          const data = await res.json();
          if (!res.ok || !data.success) {
            alert(`AI generate failed: ${data.detail || data.error || res.statusText}`);
            return;
          }
          closeAIModal();
          await selectFile(currentFile);
          if (data.manifest) {
            uiManifest = data.manifest;
            renderPreview();
          } else {
            await fetchManifest();
          }
        } catch (err) {
          alert(`AI generate error: ${err}`);
        }
      }

      function insertFromPalette(type) {
        if (previewMode !== "inspect") return;
        const target = selectedElementId && elementIndex[selectedElementId] ? elementIndex[selectedElementId] : null;
        const body = {
          path: currentFile || (target && target.source_path) || (uiManifest && uiManifest.pages && uiManifest.pages[0] && uiManifest.pages[0].source_path) || "pages/home.ai",
          op: "insert_element",
          element_id: target ? target.id : null,
          parent_id: target ? target.parent_id : null,
          position: target ? "after" : "last_child",
          new_element: { type, properties: { label: `New ${type}` } },
        };
        performTransform(body);
      }

      function deleteElement(meta) {
        if (!meta || !meta.source_path) return;
        if (!confirm("Delete this element?")) return;
        performTransform({ path: meta.source_path, op: "delete_element", element_id: meta.id });
      }

      function moveElement(meta, dir) {
        if (!meta || !meta.source_path) return;
        performTransform({ path: meta.source_path, op: "move_element", element_id: meta.id, position: dir });
      }

      function setSelected(id, pageName) {
        selectedElementId = id;
        renderPreview(); // re-render to apply highlight
        renderInspector(pageName);
      }

      function wrapInspectable(node, el, pageName) {
        if (!node || !node.id) return el;
        elementIndex[node.id] = {
          id: node.id,
          type: node.type,
          styles: node.styles || [],
          properties: node,
          page: pageName,
          page_route: (pageRegistry[pageName] && pageRegistry[pageName].route) || null,
          source_path: (pageRegistry[pageName] && pageRegistry[pageName].source_path) || node.source_path || null,
          events: node.actions || [],
          bindings: node.name ? { variable: node.name } : null,
        };
        const wrap = document.createElement('div');
        wrap.className = "ui-hover";
        if (selectedElementId === node.id) {
          wrap.classList.add('ui-selected');
          wrap.scrollIntoView({ block: "nearest" });
        }
        wrap.appendChild(el);
        wrap.addEventListener('click', (e) => {
          if (previewMode === "inspect") {
            e.stopPropagation();
            setSelected(node.id, pageName);
          }
        });
        return wrap;
      }

      function renderInspector(pageName) {
        const container = document.getElementById('inspector-body');
        if (!container) return;
        container.innerHTML = "";
        if (!selectedElementId || !elementIndex[selectedElementId]) {
          container.innerHTML = "<p style='color:var(--muted);'>Click an element in Inspector Mode to inspect it.</p>";
          return;
        }
        const meta = elementIndex[selectedElementId];
        const add = (title, items) => {
          const sec = document.createElement('div');
          sec.className = "inspector-section";
          const h = document.createElement('h4');
          h.textContent = title;
          sec.appendChild(h);
          items.forEach(txt => {
            const p = document.createElement('div');
            p.className = "inspector-item";
            p.textContent = txt;
            sec.appendChild(p);
          });
          container.appendChild(sec);
        };
        const elemLines = [
          `Type: ${meta.type}`,
          `ID: ${meta.id}`,
          meta.source_path ? `Source: ${meta.source_path}` : `Page: ${meta.page}`,
        ];
        if (meta.page_route) elemLines.push(`Route: ${meta.page_route}`);
        add("Element", elemLines);
        const styleStrings = (meta.styles || []).map(s => `${s.kind}: ${s.value}`);
        if (styleStrings.length) add("Styles", styleStrings);
        if (meta.bindings && meta.bindings.variable) {
          add("Bindings", [`Variable: ${meta.bindings.variable}`]);
        }
        if (meta.events && meta.events.length) {
          const ev = meta.events.map(e => {
            if (e.kind === "flow") {
              const args = Object.entries(e.args || {}).map(([k, v]) => `${k} → ${v.identifier || v.literal || "expr"}`).join(", ");
              return `onClick → flow '${e.target}' ${args ? "(" + args + ")" : ""}`;
            }
            return `${e.kind} → ${e.target}`;
          });
          add("Events", ev);
        }
        const actionsSec = document.createElement('div');
        actionsSec.className = "inspector-section";
        const hActions = document.createElement('h4');
        hActions.textContent = "Actions";
        actionsSec.appendChild(hActions);
        const btnDelete = document.createElement('button');
        btnDelete.className = "btn";
        btnDelete.textContent = "Delete element";
        btnDelete.onclick = () => { deleteElement(meta); };
        const btnUp = document.createElement('button');
        btnUp.className = "btn";
        btnUp.style.marginLeft = "6px";
        btnUp.textContent = "Move up";
        btnUp.onclick = () => { moveElement(meta, "up"); };
        const btnDown = document.createElement('button');
        btnDown.className = "btn";
        btnDown.style.marginLeft = "6px";
        btnDown.textContent = "Move down";
        btnDown.onclick = () => { moveElement(meta, "down"); };
        actionsSec.appendChild(btnDelete);
        actionsSec.appendChild(btnUp);
        actionsSec.appendChild(btnDown);
        container.appendChild(actionsSec);
        if (meta.source_path) {
          const link = document.createElement('button');
          link.className = "btn";
          link.textContent = "Open in Code";
          link.addEventListener('click', () => {
            selectFile(meta.source_path);
            mainTabs.forEach(t => {
              t.classList.remove('active');
              if (t.dataset.tab === 'code') t.classList.add('active');
            });
            Object.keys(contents).forEach(key => {
              contents[key].style.display = (key === 'code') ? 'block' : 'none';
            });
          });
          container.appendChild(link);
        }
      }

      async function fetchManifest() {
        previewLoading = true;
        setPreviewStatus("Loading preview…");
        renderPreview();
        try {
          const res = await fetch('/api/ui/manifest', { headers: { "X-API-Key": API_KEY } });
          if (!res.ok) throw new Error(await res.text());
          uiManifest = await res.json();
          pageRegistry = {};
          (uiManifest.pages || []).forEach(p => {
            pageRegistry[p.name] = p;
            if (p.route) pageRegistry[p.route] = p;
          });
          const initialPage = resolvePageForSelection();
          if (initialPage) {
            setRoute(initialPage.route || "/", false);
          }
          previewLoading = false;
          renderPreview();
        } catch (err) {
          previewLoading = false;
          if (uiPreview) uiPreview.textContent = "Failed to load UI manifest.";
          setPreviewStatus("Preview error");
          console.error(err);
        }
      }
      async function fetchTree() {
        try {
          const res = await fetch('/api/studio/files', { headers: { "X-API-Key": API_KEY } });
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          treeData = data.root;
          renderTree();
        } catch (err) {
          treeContainer.innerHTML = "<div style='color: var(--danger)'>Failed to load project tree.</div>";
          console.error(err);
        }
      }

      function renderTree() {
        treeContainer.innerHTML = "";
        const firstFile = { path: null };
        if (!treeData || !treeData.children || treeData.children.length === 0) {
          treeEmpty.style.display = "block";
          return;
        }
        treeEmpty.style.display = "none";

        function renderNode(node, container, depth=0) {
          const row = document.createElement('div');
          row.className = 'node';
          row.style.paddingLeft = `${depth * 12}px`;

          if (node.type === 'directory') {
            row.classList.add('folder');
            const caret = document.createElement('span');
            caret.className = 'caret open';
            row.appendChild(caret);
            const label = document.createElement('span');
            label.textContent = node.name + '/';
            row.appendChild(label);

            const childrenWrap = document.createElement('div');
            childrenWrap.style.display = 'block';
            childrenWrap.style.marginLeft = '0';

            row.addEventListener('click', (e) => {
              e.stopPropagation();
              const open = caret.classList.toggle('open');
              childrenWrap.style.display = open ? 'block' : 'none';
            });

            container.appendChild(row);
            if (node.children) {
              node.children.forEach((child) => {
                renderNode(child, childrenWrap, depth + 1);
              });
            }
            container.appendChild(childrenWrap);
          } else {
            row.dataset.file = node.path;
            row.textContent = node.name;
            row.addEventListener('click', (e) => {
              e.stopPropagation();
              selectFile(node.path);
            });
            container.appendChild(row);
            if (firstFile.path === null) firstFile.path = node.path;
          }
        }

        renderNode(treeData, treeContainer, 0);
        if (!currentFile && firstFile.path) {
          selectFile(firstFile.path);
        } else {
          highlightSelection();
        }
      }

      function highlightSelection() {
        const nodes = treeContainer.querySelectorAll('.node');
        nodes.forEach((n) => {
          if (n.dataset.file === currentFile) {
            n.classList.add('active');
          } else {
            n.classList.remove('active');
          }
        });
      }

      async function selectFile(path) {
        if (path === currentFile && !dirty) {
          highlightSelection();
          return;
        }
        try {
          setStatus("Loading...", "busy");
          const res = await fetch(`/api/studio/file?path=${encodeURIComponent(path)}`, { headers: { "X-API-Key": API_KEY } });
          if (!res.ok) throw new Error(await res.text());
          const data = await res.json();
          currentFile = data.path;
          editorEl.value = data.content;
          dirty = false;
          fileLabel.textContent = data.path;
          setStatus("Loaded", "muted");
          const targetPage = uiManifest && uiManifest.pages ? uiManifest.pages.find(p => p.source_path === data.path) : null;
          if (targetPage) {
            setRoute(targetPage.route || `/${targetPage.name}`, false);
          }
          highlightSelection();
          renderPreview();
        } catch (err) {
          setStatus("Load failed", "error");
          console.error(err);
        }
      }

      function scheduleSave() {
        dirty = true;
        fileLabel.textContent = currentFile ? `${currentFile} *` : "Unsaved";
        setStatus("Saving...", "busy");
        if (saveTimer) clearTimeout(saveTimer);
        saveTimer = setTimeout(saveNow, 800);
      }

      async function saveNow() {
        if (!currentFile) return;
        try {
          const res = await fetch('/api/studio/file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', "X-API-Key": API_KEY },
            body: JSON.stringify({ path: currentFile, content: editorEl.value })
          });
          if (!res.ok) throw new Error(await res.text());
          dirty = false;
          fileLabel.textContent = currentFile;
          setStatus("Saved", "ok");
          fetchManifest();
        } catch (err) {
          setStatus("Save failed", "error");
          console.error(err);
        }
      }

      editorEl.addEventListener('input', () => {
        if (!currentFile) return;
        setStatus("Unsaved changes", "busy");
        scheduleSave();
      });

      window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
          e.preventDefault();
          saveNow();
        }
      });

      refreshBtn.addEventListener('click', () => fetchTree());
      if (uiRefreshBtn) uiRefreshBtn.addEventListener('click', () => fetchManifest());
      deviceButtons.forEach((btn) => {
        btn.addEventListener('click', () => {
          deviceButtons.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          deviceMode = btn.dataset.device || "desktop";
          renderPreview();
        });
      });
      if (backBtn) {
        backBtn.disabled = true;
        backBtn.addEventListener('click', () => {
          if (!routeHistory.length) return;
          const prev = routeHistory.pop();
          if (currentRoute) forwardStack.push(currentRoute);
          setRoute(prev, false);
        });
      }
      if (fwdBtn) {
        fwdBtn.disabled = true;
        fwdBtn.addEventListener('click', () => {
          if (!forwardStack.length) return;
          const next = forwardStack.pop();
          if (currentRoute) routeHistory.push(currentRoute);
          setRoute(next, false);
        });
      }
      modeButtons.forEach((btn) => {
        btn.addEventListener('click', () => {
          modeButtons.forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          previewMode = btn.dataset.mode || "preview";
          selectedElementId = null;
          renderPreview();
          const palBtns = document.querySelectorAll('#palette button');
          palBtns.forEach(pb => pb.disabled = previewMode !== "inspect");
        });
      });

        const navTabs = document.querySelectorAll('.nav-tab');
        navTabs.forEach(tab => tab.addEventListener('click', () => {
          navTabs.forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          const text = tab.dataset.nav || '';
          const label = document.getElementById('editing-label');
          if (label) label.textContent = `Viewing: ${text}`;
        }));

      const mainTabs = document.querySelectorAll('.main-tab');
      const contents = {
        code: document.getElementById('content-code'),
        ui: document.getElementById('content-ui'),
        graph: document.getElementById('content-graph'),
      };
      mainTabs.forEach(tab => tab.addEventListener('click', () => {
        mainTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        Object.keys(contents).forEach(key => {
          contents[key].style.display = (tab.dataset.tab === key) ? 'block' : 'none';
        });
      }));

      fetchTree();
      fetchManifest();
      const palBtns = document.querySelectorAll('#palette button');
      palBtns.forEach(pb => pb.disabled = previewMode !== "inspect");
    </script>
  </body>
</html>
"""

    def do_GET(self):  # type: ignore[override]
        if self.path.startswith("/studio"):
            content = self.html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        self.send_response(302)
        self.send_header("Location", "/studio")
        self.end_headers()

    def log_message(self, format: str, *args):  # pragma: no cover - silence logs
        return


def start_ui_server(port: int) -> tuple[http.server.ThreadingHTTPServer, threading.Thread]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _StudioHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def run_studio(
    backend_port: int = 8000,
    ui_port: int = 4173,
    open_browser: bool = True,
    project_root: Path | None = None,
    block: bool = True,
) -> None:
    root = detect_project_root(project_root)
    if root is None:
        raise SystemExit(
            "No Namel3ss project detected. Run from a folder containing .ai files or use 'n3 init app <name>'."
        )

    _check_port_available(backend_port, "backend")
    _check_port_available(ui_port, "ui")

    backend_proc: multiprocessing.Process | None = None
    ui_server = None
    try:
        backend_proc = start_backend_process(backend_port)
    except Exception as exc:  # pragma: no cover - surface early startup issues
        raise SystemExit(f"Could not start backend: {exc}") from exc

    try:
        ui_server, _ = start_ui_server(ui_port)
    except Exception as exc:
        if backend_proc:
            backend_proc.terminate()
        raise SystemExit(f"Could not start Studio UI server: {exc}") from exc

    primary_url = "http://namel3ss.local/studio"
    fallback_url = f"http://127.0.0.1:{ui_port}/studio"
    print("\nNamel3ss Studio is running!\n")
    print(f"  • Primary URL:  {primary_url}")
    print(f"  • Fallback URL: {fallback_url}\n")
    print("  Press Ctrl+C to stop.")
    print("  If namel3ss.local does not resolve, add '127.0.0.1 namel3ss.local' to your hosts file.\n")

    if open_browser:
        with contextlib.suppress(Exception):
            webbrowser.open(primary_url)

    if not block:
        if ui_server:
            ui_server.shutdown()
        if backend_proc:
            backend_proc.terminate()
        return

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Studio...")
    finally:
        if ui_server:
            ui_server.shutdown()
        if backend_proc:
            backend_proc.terminate()


if __name__ == "__main__":  # pragma: no cover
    main()
