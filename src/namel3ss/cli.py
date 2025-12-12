"""
Command-line interface for Namel3ss (n3).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import multiprocessing
import os
import socket
import sys
import time
import webbrowser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from dataclasses import asdict
from pathlib import Path

from . import ir, lexer, parser
from . import ast_nodes
from .macros import (
    MacroExpander,
    MacroExpansionError,
    render_module_source,
    run_macro_migration,
    run_macro_tests,
)
from .secrets.manager import SecretsManager, get_default_secrets_manager
from .diagnostics import Diagnostic
from .diagnostics.runner import apply_strict_mode, collect_diagnostics, collect_lint, iter_ai_files
from .linting import LintConfig
from .lang.formatter import format_source
from .errors import ParseError
from .templates.manager import list_templates, scaffold_project
from .examples.manager import list_examples, resolve_example_path
from .version import __version__
from .memory.inspection import describe_memory_plan, describe_memory_state, inspect_memory_state
from .migration import naming as naming_migration
from .migration import data_pipelines as data_migration
from .rag.eval import run_rag_evaluation_by_name
from .tools.eval import run_tool_evaluation_by_name
from .agent.eval import run_agent_evaluation_by_name


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

    export_cmd = register("export", help="Export IR or migration scaffolds")
    export_sub = export_cmd.add_subparsers(dest="export_command", required=True)
    export_ir_cmd = export_sub.add_parser("ir", help="Export IR JSON")
    export_ir_cmd.add_argument("source", type=Path, help="Path to .ai file")
    export_ir_cmd.add_argument("--out", type=Path, help="Path to write IR JSON (stdout if omitted)")
    export_fastapi_cmd = export_sub.add_parser("fastapi", help="Generate FastAPI scaffold from IR")
    export_fastapi_cmd.add_argument("source", type=Path, help="Path to .ai file")
    export_fastapi_cmd.add_argument("--out", type=Path, required=True, help="Output directory for scaffold")

    run_cmd = register("run", help="Run an app from an .ai file")
    run_cmd.add_argument("app_name", type=str)
    run_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")

    graph_cmd = register("graph", help="Build reasoning graph for an .ai file")
    graph_cmd.add_argument("file", type=Path)

    serve_cmd = register("serve", help="Start the FastAPI server")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8000)
    serve_cmd.add_argument("--dry-run", action="store_true", help="Build app but do not start server")

    daemon_cmd = register("daemon", help="Run the Namel3ss background daemon with Studio APIs")
    daemon_cmd.add_argument("--host", default="127.0.0.1", help="Host interface for daemon (default: 127.0.0.1)")
    daemon_cmd.add_argument("--port", type=int, default=3030, help="Port for daemon (default: 3030)")
    daemon_cmd.add_argument("--project", "--project-root", dest="project_root", type=Path, help="Project root (auto-discovered by default)")
    daemon_cmd.add_argument("--app", dest="app_name", help="App name hint (logged only)")
    daemon_cmd.add_argument("--no-watch", action="store_true", help="Disable file watching/reload")

    run_agent_cmd = register("run-agent", help="Run an agent from an .ai file")
    run_agent_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    run_agent_cmd.add_argument("--agent", required=True, help="Agent name to run")

    run_flow_cmd = register("run-flow", help="Run a flow from an .ai file")
    run_flow_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    run_flow_cmd.add_argument("--flow", required=True, help="Flow name to run")

    mem_inspect_cmd = register("memory-inspect", help="Inspect memory plan/state for an AI call")
    mem_inspect_cmd.add_argument("--file", type=Path, required=True, help="Path to an .ai file to load")
    mem_inspect_cmd.add_argument(
        "--ai",
        "--ai-id",
        dest="ai_id",
        help="AI call identifier (defaults to the first AI in the file)",
    )
    mem_inspect_cmd.add_argument(
        "--session-id",
        help="Session identifier to inspect (required for per-session data)",
    )
    mem_inspect_cmd.add_argument("--user-id", help="User identifier for per-user memory scopes")
    mem_inspect_cmd.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum entries to return per memory kind (default: 25)",
    )
    mem_inspect_cmd.add_argument(
        "--plan-only",
        action="store_true",
        help="Only print the memory plan/configuration without reading stored entries",
    )

    migrate_cmd = register("migrate", help="Migration helpers")
    migrate_sub = migrate_cmd.add_subparsers(dest="migrate_command", required=True)
    migrate_naming_cmd = migrate_sub.add_parser(
        "naming-standard",
        help="Rewrite legacy headers/assignments to the English syntax (Naming Standard v1).",
    )
    migrate_naming_cmd.add_argument("--path", required=True, type=Path, help="Path to a file or directory containing .ai sources")
    migrate_naming_cmd.add_argument("--dry-run", action="store_true", help="Show what would change (default)")
    migrate_naming_cmd.add_argument("--write", action="store_true", help="Apply changes in place")
    migrate_naming_cmd.add_argument("--no-backup", action="store_true", help="Skip writing .bak backups when --write is used")
    migrate_naming_cmd.add_argument(
        "--fix-names",
        action="store_true",
        help="Conservatively rename simple camelCase locals to snake_case (or emit suggestions).",
    )
    migrate_data_cmd = migrate_sub.add_parser(
        "data-pipelines",
        help="Rewrite legacy data/collection syntax (all ... from ..., map(...)) into collection pipelines where possible.",
    )
    migrate_data_cmd.add_argument("paths", nargs="*", type=Path, help="Files or directories containing .ai sources (defaults to current directory)")
    migrate_data_cmd.add_argument("--write", action="store_true", help="Apply changes in place")
    migrate_data_cmd.add_argument("--no-backup", action="store_true", help="Skip writing .bak backups when --write is used")
    page_ui_cmd = register("page-ui", help="Render UI for a page")
    page_ui_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    page_ui_cmd.add_argument("--page", required=True, help="Page name to render")

    meta_cmd = register("meta", help="Show program metadata")
    meta_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")

    rag_eval_cmd = register("rag-eval", help="Run a RAG evaluation defined in the .ai file")
    rag_eval_cmd.add_argument("evaluation", help="Name of the rag evaluation to run")
    rag_eval_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    rag_eval_cmd.add_argument("--limit", type=int, help="Only evaluate the first N rows")
    rag_eval_cmd.add_argument("--output", choices=["json"], help="Use 'json' for machine-readable output")

    tool_eval_cmd = register("tool-eval", help="Run a tool evaluation defined in the .ai file")
    tool_eval_cmd.add_argument("evaluation", help="Name of the tool evaluation to run")
    tool_eval_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    tool_eval_cmd.add_argument("--limit", type=int, help="Only evaluate the first N rows")
    tool_eval_cmd.add_argument("--output", choices=["json"], help="Use 'json' for machine-readable output")

    agent_eval_cmd = register("agent-eval", help="Run an agent evaluation defined in the .ai file")
    agent_eval_cmd.add_argument("evaluation", help="Name of the agent evaluation to run")
    agent_eval_cmd.add_argument("--file", type=Path, required=True, help="Path to .ai file")
    agent_eval_cmd.add_argument("--limit", type=int, help="Only evaluate the first N rows")
    agent_eval_cmd.add_argument("--output", choices=["json"], help="Use 'json' for machine-readable output")

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
    lint_cmd.add_argument("--strict", action="store_true", help="Treat warnings as errors")

    macro_cmd = register("macro", help="Macro utilities (expand, test)")
    macro_sub = macro_cmd.add_subparsers(dest="macro_command", required=True)
    macro_expand_cmd = macro_sub.add_parser("expand", help="Expand macros and print the expanded source")
    macro_expand_cmd.add_argument("file", type=Path, help="Path to .ai source")
    macro_expand_cmd.add_argument("--macro", dest="macro_name", help="Only expand uses of this macro name")
    macro_test_cmd = macro_sub.add_parser("test", help="Run macro tests defined in a file")
    macro_test_cmd.add_argument("file", type=Path, help="Path to .ai source containing macro tests")
    macro_migrate_cmd = macro_sub.add_parser("migrate", help="Run macro plan migrations (no-op scaffold)")
    macro_migrate_cmd.add_argument("--macro", dest="macro_name", help="Macro name to migrate")
    macro_migrate_cmd.add_argument("--from", dest="from_version", help="Current version", default=None)
    macro_migrate_cmd.add_argument("--to", dest="to_version", help="Target version", default=None)

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

    doctor_cmd = register("doctor", help="Run environment and configuration health checks")

    studio_cmd = register("studio", help="Start Namel3ss Studio (packaged static build).")
    studio_cmd.add_argument("mode", nargs="?", choices=["dev"], help="Use dev mode to keep the daemon watcher active.")
    studio_cmd.add_argument("--backend-port", type=int, default=8000, help="Port for backend runtime (default: 8000)")
    studio_cmd.add_argument(
        "--ui-port",
        "--port",
        dest="ui_port",
        type=int,
        default=3333,
        help="Deprecated: Studio is served by the backend; this flag is ignored.",
    )
    studio_cmd.add_argument("--project", dest="project_root", type=Path, help="Path to project root (auto-discovered by default)")
    studio_cmd.add_argument("--app", dest="app_name", help="App name hint for Studio (logged only)")
    studio_cmd.add_argument(
        "--no-open-browser",
        "--no-open",
        dest="no_open_browser",
        action="store_true",
        help="Do not open a browser automatically",
    )

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


def _load_ir_program(path: Path) -> ir.IRProgram:
    source = path.read_text(encoding="utf-8")
    module = parser.Parser(lexer.Lexer(source, filename=str(path)).tokenize()).parse_module()
    return ir.ast_to_ir(module)


def _load_engine(path: Path):
    from .runtime.engine import Engine

    return Engine.from_file(path)


def export_ir_json(source: Path, out_path: Path | None = None) -> None:
    program = _load_ir_program(source)
    payload = asdict(program)
    text = json.dumps(payload, indent=2, sort_keys=True)
    if out_path:
        out_path.write_text(text, encoding="utf-8")
    else:
        print(text)


def _sanitize_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)


def generate_fastapi_scaffold(source: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    program = _load_ir_program(source)
    flows_module = []
    flow_funcs = []
    for flow in program.flows.values():
        func_name = f"flow_{_sanitize_name(flow.name)}"
        flow_funcs.append((flow.name, func_name))
        steps_comment = []
        for step in flow.steps:
            target = getattr(step, "target", None) or getattr(step, "name", "step")
            kind = getattr(step, "kind", "step")
            steps_comment.append(f"# - {kind}: {target}")
        steps_block = "\n    ".join(steps_comment) or "# - (no steps captured)"
        flows_module.append(
            f"async def {func_name}(payload: dict) -> dict:\n    \"\"\"Flow '{flow.name}' stub generated from Namel3ss IR.\"\"\"\n    {steps_block}\n    return {{\"flow\": \"{flow.name}\", \"input\": payload}}\n\n"
        )
    flows_py = "\n".join(flows_module) or "\nasync def flow_default(payload: dict) -> dict:\n    return {\"flow\": \"default\", \"input\": payload}\n"
    (out_dir / "flows.py").write_text(flows_py, encoding="utf-8")

    imports = "\n".join([f"from flows import {fn}" for _, fn in flow_funcs]) if flow_funcs else "from flows import flow_default"
    mapping_entries = ",\n    ".join([f"\"{name}\": {fn}" for name, fn in flow_funcs]) if flow_funcs else "\"default\": flow_default"
    main_py = f"""try:
    from fastapi import FastAPI, HTTPException
except ImportError:  # pragma: no cover - fallback for environments without FastAPI
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail
    class FastAPI:
        def __init__(self, *args, **kwargs):
            self.routes = {{}}
        def post(self, path: str):
            def decorator(func):
                self.routes[path] = func
                return func
            return decorator

app = FastAPI()
{imports}

flows_map = {{
    {mapping_entries}
}}

@app.post('/flows/{{flow_name}}')
async def run_flow(flow_name: str, payload: dict):
    handler = flows_map.get(flow_name)
    if handler is None:
        raise HTTPException(status_code=404, detail='Flow not found')
    return await handler(payload)

@app.get('/')
async def root():
    return {{'status': 'ok', 'flows': list(flows_map.keys())}}
"""  # noqa: E501
    (out_dir / "main.py").write_text(main_py, encoding="utf-8")


def run_doctor() -> int:
    from platform import python_version
    from .version import __version__, IR_VERSION

    issues: list[tuple[str, str]] = []
    py_ver = python_version()
    py_status = "OK" if py_ver >= "3.10" else "WARNING"
    issues.append((py_status, f"Python version: {py_ver} (minimum recommended 3.10)"))
    issues.append(("OK", f"Namel3ss version: {__version__}"))
    issues.append(("OK", f"IR version: {IR_VERSION}"))

    provider_envs = ["N3_OPENAI_API_KEY", "OPENAI_API_KEY", "N3_ANTHROPIC_API_KEY", "N3_GEMINI_API_KEY"]
    missing = [env for env in provider_envs if not os.getenv(env)]
    if len(missing) == len(provider_envs):
        issues.append(("WARNING", "No provider API keys found in environment (set N3_OPENAI_API_KEY, N3_ANTHROPIC_API_KEY, etc.)."))
    else:
        issues.append(("OK", "Provider API keys detected in environment."))

    manifest = Path("examples/golden_examples.json")
    if manifest.exists():
        issues.append(("OK", f"Golden manifest present at {manifest}"))
    else:
        issues.append(("WARNING", "Golden manifest (examples/golden_examples.json) not found."))

    has_error = any(status == "ERROR" for status, _ in issues)
    for status, msg in issues:
        print(f"[{status}] {msg}")
    return 1 if has_error else 0


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

    if args.command == "macro":
        if args.macro_command == "expand":
            module = load_module_from_file(args.file)
            if getattr(args, "macro_name", None):
                filtered: list[ast_nodes.Declaration] = []
                for decl in module.declarations:
                    if isinstance(decl, ast_nodes.MacroUse):
                        if decl.macro_name == args.macro_name:
                            filtered.append(decl)
                        continue
                    if isinstance(decl, ast_nodes.MacroDecl):
                        filtered.append(decl)
                        continue
                    if isinstance(decl, ast_nodes.MacroTestDecl):
                        continue
                    filtered.append(decl)
                module = ast_nodes.Module(declarations=filtered)
            try:
                expanded = MacroExpander(None).expand_module(module)
            except MacroExpansionError as exc:
                raise SystemExit(str(exc)) from exc
            except Exception as exc:  # pragma: no cover - safety net
                raise SystemExit(str(exc)) from exc
            print(render_module_source(expanded))
            return
        if args.macro_command == "test":
            module = load_module_from_file(args.file)
            passed, failures = run_macro_tests(module, ai_callback=None)
            if not passed and not failures:
                raise SystemExit("No macro tests found in file.")
            if failures:
                for msg in failures:
                    print(f"FAIL: {msg}")
                raise SystemExit(1)
            print(f"Passed {len(passed)} macro test(s).")
            return
        if args.macro_command == "migrate":
            message = run_macro_migration(getattr(args, "macro_name", None), args.from_version, args.to_version)
            print(message)
            return

    if args.command == "export":
        if args.export_command == "ir":
            export_ir_json(args.source, out_path=args.out)
            return
        if args.export_command == "fastapi":
            generate_fastapi_scaffold(args.source, args.out)
            print(f"FastAPI scaffold written to {args.out}")
            return

    if args.command == "run":
        engine = _load_engine(args.file)
        result = engine.run_app(args.app_name)
        print(json.dumps(result, indent=2))
        return

    if args.command == "graph":
        engine = _load_engine(args.file)
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

    if args.command == "migrate":
        if args.migrate_command == "naming-standard":
            target_path: Path = args.path
            if not target_path.exists():
                print(f"Path '{target_path}' does not exist.", file=sys.stderr)
                return
            results = []
            if target_path.is_file() and target_path.suffix == ".ai":
                results.append(
                    naming_migration.migrate_file(
                        target_path,
                        write=args.write,
                        backup=not args.no_backup,
                        apply_name_fixes=args.fix_names,
                    )
                )
            else:
                results = naming_migration.migrate_path(
                    target_path,
                    write=args.write,
                    backup=not args.no_backup,
                    apply_name_fixes=args.fix_names,
                )
            changed = sum(1 for r in results if r.changed)
            header_total = sum(getattr(r, "header_rewrites", 0) for r in results)
            let_total = sum(getattr(r, "let_rewrites", 0) for r in results)
            set_total = sum(getattr(r, "set_rewrites", 0) for r in results)
            if args.write:
                print(f"Migrated {changed} file(s). Headers: {header_total}, let: {let_total}, set: {set_total}.")
                for r in results:
                    if r.renames:
                        for old, new in r.renames.items():
                            print(f"Renaming '{old}' -> '{new}' in {r.path}")
            else:
                print("Dry run. Re-run with --write to apply changes.")
                for r in results:
                    if r.changed or (r.suggested_names):
                        print(f"- {r.path}: headers={r.header_rewrites}, let={r.let_rewrites}, set={r.set_rewrites}")
                        if r.suggested_names:
                            for old, new in r.suggested_names:
                                print(f"  Suggest: rename {old} -> {new}")
            return
        if args.migrate_command == "data-pipelines":
            targets = args.paths or [Path(".")]
            results = []
            for target in targets:
                if not target.exists():
                    print(f"Path '{target}' does not exist.", file=sys.stderr)
                    continue
                if target.is_file() and target.suffix == ".ai":
                    results.append(
                        data_migration.migrate_file(target, write=args.write, backup=not args.no_backup)
                    )
                else:
                    results.extend(data_migration.migrate_path(target, write=args.write, backup=not args.no_backup))
            rewrites = sum(r.rewrites for r in results)
            if args.write:
                print(f"Migrated {rewrites} legacy data block(s) across {len(results)} file(s).")
            else:
                print("Dry run. Re-run with --write to apply changes.")
            for r in results:
                for detail in r.details:
                    print(f"- {r.path}: {detail}")
                for warning in r.warnings:
                    print(f"- {r.path}: {warning}")
            return
        print("Unknown migrate subcommand", file=sys.stderr)
        return

    if args.command == "serve":
        try:
            from .server import create_app
        except Exception as exc:  # pragma: no cover - load-time guard
            raise SystemExit(f"Failed to import server: {exc}") from exc
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

    if args.command == "daemon":
        project_root = _resolve_project_root(args.project_root, allow_bootstrap=True)
        ai_files = iter_ai_files([project_root])
        _check_port_available(args.port, "daemon", flag_hint="n3 daemon --port <port>")
        daemon_proc: multiprocessing.Process | None = None
        try:
            daemon_proc = start_daemon_process(args.port, project_root, host=args.host, watch=not args.no_watch)
        except Exception as exc:
            raise SystemExit(f"Failed to start daemon: {exc}") from exc

        ok, err = _wait_for_http(f"http://{args.host}:{args.port}/health")
        if not ok:
            _stop_process(daemon_proc, "daemon")
            raise SystemExit(f"Daemon did not start on port {args.port}. {err or 'Timed out waiting for /health.'}")

        status_payload, status_err = _fetch_studio_status(f"http://{args.host}:{args.port}")

        print("\nNamel3ss daemon is running!\n")
        print(f"[âœ“] Project root: {project_root}")
        if getattr(args, "app_name", None):
            print(f"[âœ“] Using app:    \"{args.app_name}\"")
        if ai_files:
            print(f"[âœ“] Watching {len(ai_files)} .ai file(s)")
        print(f"[âœ“] Daemon:       http://{args.host}:{args.port}")
        for msg in _studio_status_messages(status_payload):
            print(msg)
        if status_payload is None and status_err:
            print(f"[!] Could not fetch daemon status: {status_err}")
        print("Press Ctrl+C to stop the daemon.\n")

        try:
            while True:
                time.sleep(1)
                if daemon_proc and not daemon_proc.is_alive():
                    print("Daemon exited unexpectedly. Check logs above.")
                    break
        except KeyboardInterrupt:
            print("\nStopping daemonâ€¦")
        finally:
            _stop_process(daemon_proc, "daemon")
            print("Done.")
        return

    if args.command == "run-agent":
        engine = _load_engine(args.file)
        result = engine.execute_agent(args.agent)
        print(json.dumps(result, indent=2))
        return

    if args.command == "run-flow":
        engine = _load_engine(args.file)
        result = engine.execute_flow(args.flow)
        print(json.dumps(result, indent=2))
        return

    if args.command == "rag-eval":
        engine = _load_engine(args.file)
        try:
            result = run_rag_evaluation_by_name(
                engine.program, engine.flow_engine, args.evaluation, limit=getattr(args, "limit", None)
            )
        except Exception as exc:
            raise SystemExit(str(exc))
        if getattr(args, "output", None) == "json":
            print(json.dumps(asdict(result), indent=2))
            return
        print(f"RAG evaluation: {result.name}")
        print(f"Pipeline: {result.pipeline}")
        print(f"Dataset: frame \"{result.dataset_frame}\" ({result.num_rows} rows)")
        if result.aggregates:
            print("\nMetrics (averages):")
            for name, agg in result.aggregates.items():
                mean = agg.get("mean", 0)
                count = agg.get("count", 0)
                print(f"  - {name}: {mean:.2f} ({count} scored rows)")
        if result.rows:
            print("\nSample rows:")
            for idx, row in enumerate(result.rows[: min(3, len(result.rows))], start=1):
                metrics = ", ".join(
                    f"{k}: {v:.2f}" for k, v in row.metrics.items() if isinstance(v, (int, float))
                )
                print(f"  [{idx}] question: {row.question}")
                if metrics:
                    print(f"      metrics: {metrics}")
        return

    if args.command == "tool-eval":
        engine = _load_engine(args.file)
        try:
            result = run_tool_evaluation_by_name(
                engine.program, engine.flow_engine, args.evaluation, limit=getattr(args, "limit", None)
            )
        except Exception as exc:
            raise SystemExit(str(exc))
        if getattr(args, "output", None) == "json":
            print(json.dumps(asdict(result), indent=2))
            return
        print(f"Tool evaluation: {result.name}")
        print(f"Tool: {result.tool}")
        print(f"Dataset: frame \"{result.dataset_frame}\" ({result.num_rows} rows)")
        if result.metrics:
            print("\nMetrics:")
            for name, value in result.metrics.items():
                if isinstance(value, float):
                    print(f"  - {name}: {value:.3f}")
                else:
                    print(f"  - {name}: {value}")
        if result.rows:
            print("\nSample rows:")
            for idx, row in enumerate(result.rows[: min(3, len(result.rows))], start=1):
                status = f"status={row.status}" if row.status is not None else "status=?"
                print(f"  [{idx}] success={row.success} {status} latency={row.latency_ms:.1f}ms")
                if row.error:
                    print(f"      error: {row.error}")
        return
    if args.command == "agent-eval":
        engine = _load_engine(args.file)
        try:
            result = run_agent_evaluation_by_name(
                engine.program, engine.flow_engine, args.evaluation, limit=getattr(args, "limit", None)
            )
        except Exception as exc:
            raise SystemExit(str(exc))
        if getattr(args, "output", None) == "json":
            print(json.dumps(asdict(result), indent=2))
            return
        print(f"Agent evaluation: {result.name}")
        print(f"Agent: {result.agent}")
        print(f"Dataset: frame \"{result.dataset_frame}\" ({result.num_rows} rows)")
        if result.metrics:
            print("\nMetrics:")
            for name, value in result.metrics.items():
                if isinstance(value, float):
                    print(f"  - {name}: {value:.3f}")
                else:
                    print(f"  - {name}: {value}")
        if result.rows:
            print("\nSample rows:")
            for idx, row in enumerate(result.rows[: min(3, len(result.rows))], start=1):
                print(
                    f"  [{idx}] success={row.success} latency={row.latency_seconds:.2f}s expected={row.expected_answer} answer={row.answer}"
                )
                if row.error:
                    print(f"      error: {row.error}")
        return

    if args.command == "memory-inspect":
        engine = _load_engine(args.file)
        ai_calls = getattr(engine.program, "ai_calls", {})
        ai_name = getattr(args, "ai_id", None) or next(iter(ai_calls), None)
        if not ai_name:
            raise SystemExit("No AI calls found in the provided file.")
        if ai_name not in ai_calls:
            raise SystemExit(f"AI '{ai_name}' not found in the provided file.")
        ai_call = ai_calls[ai_name]
        plan = describe_memory_plan(ai_call)
        output: Dict[str, Any] = {
            "ai": ai_name,
            "plan": plan,
            "state": None,
        }
        include_state = not getattr(args, "plan_only", False) and (getattr(args, "session_id", None) or getattr(args, "user_id", None))
        if include_state:
            try:
                limit = max(1, int(getattr(args, "limit", 25)))
            except (TypeError, ValueError):
                raise SystemExit("--limit must be a positive integer")
            try:
                output["state"] = describe_memory_state(
                    engine,
                    ai_call,
                    session_id=getattr(args, "session_id", None),
                    user_id=getattr(args, "user_id", None),
                    limit=limit,
                )
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
        print(json.dumps(output, indent=2))
        return

    if args.command == "page-ui":
        engine = _load_engine(args.file)
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
        engine = _load_engine(args.file)
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
        lint_results, lint_summary = apply_strict_mode(lint_results, args.strict)
        error_count = lint_summary["errors"]
        success = error_count == 0
        if args.json:
            print(
                json.dumps(
                    {
                        "success": success,
                        "lint": [d.to_dict() for d in lint_results],
                        "summary": lint_summary,
                    },
                    indent=2,
                )
            )
        else:
            if not lint_results:
                print("No lint findings.")
            for lint in lint_results:
                print(_format_diagnostic(lint))
                if lint.hint:
                    print(f"  hint: {lint.hint}")
            warn_count = lint_summary["warnings"]
            info_count = lint_summary["infos"]
            print(f"Summary: {error_count} errors, {warn_count} warnings, {info_count} infos across {len(ai_files)} files.")
        if not success:
            raise SystemExit(1)
        return

    if args.command == "doctor":
        raise SystemExit(run_doctor())

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

        secrets = get_default_secrets_manager()
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
        if getattr(args, "mode", None) == "dev":
            run_studio_dev(
                backend_port=args.backend_port,
                ui_port=args.ui_port,
                open_browser=not args.no_open_browser,
                project_root=getattr(args, "project_root", None),
                app_name=getattr(args, "app_name", None),
            )
        else:
            run_studio(
                backend_port=args.backend_port,
                ui_port=args.ui_port,
                open_browser=not args.no_open_browser,
                project_root=getattr(args, "project_root", None),
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
_PROJECT_CONFIG_FILES = ("namel3ss.config.json", "namel3ss.toml", "namel3ss.config.toml")
_PROJECT_SCAN_IGNORES = {".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}


def _has_ai_files(base: Path) -> bool:
    if base.is_file():
        return base.suffix == ".ai"
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in _PROJECT_SCAN_IGNORES]
        for name in files:
            if name.endswith(".ai"):
                return True
    return False


def discover_project_root(start: Path | None = None) -> Path | None:
    """
    Walk up from the starting directory until we find a Namel3ss config or any .ai file.
    """
    base = (start or Path.cwd()).resolve()
    for candidate in [base, *base.parents]:
        if any((candidate / cfg).exists() for cfg in _PROJECT_CONFIG_FILES):
            return candidate
        if _has_ai_files(candidate):
            return candidate
    return None


def detect_project_root(start: Path | None = None) -> Path | None:
    # Backwards-compatible wrapper.
    return discover_project_root(start)


def _prompt_yes_no(prompt: str) -> bool:
    try:
        reply = input(prompt).strip().lower()
    except EOFError:
        return False
    return reply in {"y", "yes"}


def _bootstrap_starter_project(target_dir: Path) -> Path | None:
    target_dir = target_dir.resolve()
    if not sys.stdin.isatty():
        print("No Namel3ss project found and cannot prompt in non-interactive mode. Create an .ai file and re-run.")
        return None
    if not target_dir.exists():
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"Cannot create directory {target_dir}: {exc}")
            return None
    if not os.access(target_dir, os.W_OK):
        print(f"Cannot write to {target_dir}. Please pick a writable directory or run with --project <path>.")
        return None

    print("I couldnâ€™t find any Namel3ss .ai files here.")
    if not _prompt_yes_no("Create a starter app and open Studio? (y/N) "):
        print("No files created. You can run `n3 init app-basic` or add an .ai file manually.")
        return None

    starter_paths = [target_dir / "app.ai", target_dir / "starter.ai", target_dir / "main.ai"]
    chosen: Path | None = None
    for candidate in starter_paths:
        if not candidate.exists():
            chosen = candidate
            break
    if chosen is None:
        print("A project already exists here. Remove or rename existing .ai files and try again.")
        return None

    starter_app = '''app is "starter":
  page is "home":
    heading "Welcome to Namel3ss"
    text "Edit this starter page to get going."
  flow is "hello":
    step is "greet":
      log info "Hello from Namel3ss"
'''
    try:
        chosen.write_text(starter_app, encoding="utf-8")
    except OSError as exc:
        print(f"Failed to write starter file {chosen}: {exc}")
        return None

    print(f"Created starter app at {chosen}. Launching Studioâ€¦")
    try:
        from namel3ss.studio.logs import log_event, LogBuffer
    except Exception:
        pass
    else:
        buf = LogBuffer(max_events=10)
        log_event(buf, "starter_project_created", path=str(chosen))
    return target_dir


def _resolve_project_root(
    project_arg: Path | None,
    allow_bootstrap: bool = False,
    base_path: Path | None = None,
) -> Path:
    if project_arg:
        project_arg = project_arg.expanduser().resolve()
        if not project_arg.exists() or not project_arg.is_dir():
            raise SystemExit(f"Project path not found: {project_arg}")
        if _has_ai_files(project_arg):
            return project_arg
        if allow_bootstrap:
            bootstrapped = _bootstrap_starter_project(project_arg)
            if bootstrapped:
                return bootstrapped
        raise SystemExit(f"No .ai files found under {project_arg}. Add an .ai file or run `n3 init app-basic`.")
    root = discover_project_root(base_path)
    if root:
        if _has_ai_files(root):
            return root
        if allow_bootstrap:
            bootstrapped = _bootstrap_starter_project(root)
            if bootstrapped:
                return bootstrapped
        raise SystemExit(f"No .ai files found under {root}. Add an .ai file or run `n3 init app-basic`.")
    if allow_bootstrap:
        bootstrapped = _bootstrap_starter_project(base_path or Path.cwd())
        if bootstrapped:
            return bootstrapped
    raise SystemExit(
        "No Namel3ss project found. Run in a directory with .ai files, pass --project <path>, or run `n3 init app-basic`."
    )


def _check_port_available(port: int, name: str, flag_hint: str | None = None) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except PermissionError:
            hint = f" Try {flag_hint}." if flag_hint else ""
            raise SystemExit(f"Port {port} requires elevated privileges.{hint}")
        except OSError:
            hint = f" Try {flag_hint}." if flag_hint else f" Try: n3 studio --{name}-port <other>."
            raise SystemExit(f"Port {port} is already in use.{hint}")


def _wait_for_http(url: str, timeout: float = 8.0, interval: float = 0.4) -> tuple[bool, str | None]:
    deadline = time.time() + timeout
    last_error: str | None = None
    while time.time() < deadline:
        try:
            req = Request(url, headers={"User-Agent": "namel3ss-cli/1"})
            with urlopen(req, timeout=interval) as resp:  # nosec - controlled local call
                if resp.status < 500:
                    return True, None
        except Exception as exc:  # pragma: no cover - transient startup errors
            last_error = str(exc)
            time.sleep(interval)
    return False, last_error


def _fetch_studio_status(base_url: str, timeout: float = 5.0) -> tuple[dict | None, str | None]:
    try:
        req = Request(
            urljoin(base_url, "/api/studio/status"),
            headers={"User-Agent": "namel3ss-cli/1", "Accept": "application/json"},
        )
        with urlopen(req, timeout=timeout) as resp:  # nosec - local call
            if resp.status >= 500:
                return None, f"{resp.status} {resp.reason}"
            content = resp.read()
            if not content:
                return None, "empty response"
            return json.loads(content.decode("utf-8")), None
    except Exception as exc:  # pragma: no cover - network failures
        return None, str(exc)


def _stop_process(proc: multiprocessing.Process | None, name: str, timeout: float = 3.0) -> None:
    if not proc:
        return
    try:
        proc.terminate()
        proc.join(timeout)
    except Exception:
        pass


def _studio_status_messages(status: dict | None) -> list[str]:
    if not status:
        return []
    messages: list[str] = []
    ir_status = status.get("ir_status")
    if ir_status == "error":
        err = status.get("ir_error") or {}
        loc_parts: list[str] = []
        if err.get("file"):
            loc_parts.append(str(err["file"]))
        if err.get("line") is not None:
            loc_parts.append(str(err["line"]))
        if err.get("column") is not None:
            loc_parts.append(str(err["column"]))
        location = ":".join(loc_parts)
        prefix = f"{location}: " if location else ""
        msg = err.get("message") or "Your Namel3ss program could not be parsed."
        messages.append("[!] Your .ai files contain errors.\n    See details below:\n    - " + prefix + msg)
        messages.append("    Fix the error and save the file; the daemon will reload automatically.")
    elif status.get("ai_files", 0) == 0:
        messages.append("[!] No .ai files found. Add an .ai file or run `n3 init app-basic`.")
    else:
        ai_paths = status.get("ai_file_paths") or []
        if len(ai_paths) == 1 and ai_paths[0] in {"starter.ai", "app.ai", "main.ai"} and not status.get("config_file_found"):
            messages.append("Starter project created. Edit starter.ai to begin.")
    watcher_supported = status.get("watcher_supported", True)
    watcher_active = status.get("watcher_active", False)
    if not watcher_supported:
        messages.append("[!] File system watcher unavailable; IR will not auto-reload.")
    elif not watcher_active:
        messages.append("[!] File system watcher inactive; changes will not auto-reload.")
    if not status.get("studio_static_available", True):
        messages.append(
            "[!] Packaged Studio static assets not found.\n"
            "    Reinstall namel3ss to restore bundled Studio assets."
        )
    return messages


def run_daemon_server(host: str, port: int, project_root: Path, watch: bool = True, log_level: str = "info") -> None:
    from namel3ss.studio.daemon import StudioDaemon
    from namel3ss.server import create_app
    import uvicorn

    daemon = StudioDaemon(project_root.resolve())
    daemon.ensure_program(raise_on_error=False)
    app = create_app(project_root=project_root.resolve(), daemon_state=daemon)
    if watch:
        daemon.start_watcher()
    try:
        uvicorn.run(app, host=host, port=port, log_level=log_level)
    finally:
        daemon.stop_watcher()


def _daemon_process_entry(host: str, port: int, project_root: str, watch: bool) -> None:
    try:
        run_daemon_server(host, port, Path(project_root), watch=watch, log_level="warning")
    except Exception as exc:  # pragma: no cover - best-effort logging
        print(f"Daemon failed: {exc}", file=sys.stderr)


def start_daemon_process(
    port: int, project_root: Path, host: str = "127.0.0.1", watch: bool = True
) -> multiprocessing.Process:
    proc = multiprocessing.Process(
        target=_daemon_process_entry,
        args=(host, port, str(project_root), watch),
        daemon=True,
    )
    proc.start()
    return proc



def run_studio_dev(
    backend_port: int = 8000,
    ui_port: int = 3333,
    open_browser: bool = True,
    project_root: Path | None = None,
    app_name: str | None = None,
    block: bool = True,
) -> None:
    root = _resolve_project_root(project_root, allow_bootstrap=True)
    _check_port_available(backend_port, "backend", flag_hint="n3 studio dev --backend-port <port>")

    backend_proc: multiprocessing.Process | None = None
    try:
        backend_proc = start_daemon_process(backend_port, root.resolve(), watch=True)
    except Exception as exc:  # pragma: no cover - early startup guard
        raise SystemExit(f"Could not start backend daemon: {exc}") from exc

    ok, err = _wait_for_http(f"http://127.0.0.1:{backend_port}/health")
    if not ok:
        _stop_process(backend_proc, "daemon")
        raise SystemExit(f"Daemon did not start on port {backend_port}. {err or 'Timed out waiting for /health.'}")

    status_payload, status_err = _fetch_studio_status(f"http://127.0.0.1:{backend_port}")
    status_messages = _studio_status_messages(status_payload)

    active_url = f"http://127.0.0.1:{backend_port}/studio"
    ai_files = iter_ai_files([root])
    print("\nNamel3ss Studio (dev) is running!\n")
    print(f"[âœ“] Project root: {root}")
    if app_name:
        print(f"[âœ“] Using app:    \"{app_name}\"")
    if ai_files:
        print(f"[âœ“] Watching {len(ai_files)} .ai file(s)")
    print(f"[âœ“] Runtime daemon: http://127.0.0.1:{backend_port}")
    print(f"[âœ“] Studio UI:      {active_url}")
    for msg in status_messages:
        print(msg)
    if status_payload is None and status_err:
        print(f"[!] Could not fetch daemon status: {status_err}")
    if ui_port != backend_port:
        print(f"[i] UI port flag is ignored; Studio is served by the backend on {backend_port}.")
    print("Press Ctrl+C to stop both the daemon and Studio.\n")

    if open_browser:
        with contextlib.suppress(Exception):
            webbrowser.open(active_url)

    if not block:
        _stop_process(backend_proc, "daemon")
        return

    try:
        while True:
            time.sleep(1)
            if backend_proc and not backend_proc.is_alive():
                print("Daemon exited unexpectedly. Check logs above.")
                break
    except KeyboardInterrupt:
        print("\nShutting down Studio and daemonâ€¦")
    finally:
        _stop_process(backend_proc, "daemon")
        print("Done.")


def run_studio(
    backend_port: int = 8000,
    ui_port: int = 3333,
    open_browser: bool = True,
    project_root: Path | None = None,
    block: bool = True,
) -> None:
    root = _resolve_project_root(project_root, allow_bootstrap=False)

    _check_port_available(backend_port, "backend", flag_hint="n3 studio --backend-port <port>")

    backend_proc: multiprocessing.Process | None = None
    try:
        backend_proc = start_daemon_process(backend_port, root.resolve(), watch=True)
    except Exception as exc:  # pragma: no cover - surface early startup issues
        raise SystemExit(f"Could not start backend: {exc}") from exc

    ok, err = _wait_for_http(f"http://127.0.0.1:{backend_port}/health")
    if not ok:
        _stop_process(backend_proc, "daemon")
        raise SystemExit(f"Daemon did not start on port {backend_port}. {err or 'Timed out waiting for /health.'}")

    status_payload, status_err = _fetch_studio_status(f"http://127.0.0.1:{backend_port}")
    status_messages = _studio_status_messages(status_payload)

    active_url = f"http://127.0.0.1:{backend_port}/studio"
    print("\nNamel3ss Studio is running!\n")
    print(f"  â€¢ Studio URL: {active_url}\n")
    for msg in status_messages:
        print(f"  {msg}")
    if status_payload is None and status_err:
        print(f"  [!] Could not fetch daemon status: {status_err}")
    if ui_port != backend_port:
        print(f"  [i] UI port flag is ignored; Studio is served by the backend on {backend_port}.\n")
    print("  Press Ctrl+C to stop.\n")

    if open_browser:
        with contextlib.suppress(Exception):
            webbrowser.open(active_url)

    if not block:
        _stop_process(backend_proc, "daemon")
        return

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Studio...")
    finally:
        _stop_process(backend_proc, "daemon")


if __name__ == "__main__":  # pragma: no cover
    main()
