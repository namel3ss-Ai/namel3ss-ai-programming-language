"""
FastAPI surface for Namel3ss V3.
"""

from __future__ import annotations

import os
import asyncio
import json
import importlib.resources as resources
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict

from . import ir, lexer, parser
from .ai.registry import ModelRegistry
from .config import N3Config, ProvidersConfig, load_config
from .errors import ParseError, Namel3ssError
from .lang.formatter import format_source
from .flows.triggers import FlowTrigger, TriggerManager
from .runtime.engine import Engine
from .runtime.context import (
    DEFAULT_SHORT_TERM_WINDOW,
    ExecutionContext,
    clear_recall_snapshot,
    filter_items_by_retention,
    filter_turns_by_retention,
    get_last_recall_snapshot,
)
from .ui.renderer import UIRenderer
from .ui.runtime import UIEventRouter
from .ui.components import UIEvent, UIContext
from .obs.tracer import Tracer
from .observability.tracing import default_tracer
from .security import (
    API_KEY_HEADER,
    Principal,
    Role,
    can_run_app,
    can_run_flow,
    can_view_pages,
    can_view_traces,
    get_principal,
)
from .distributed.queue import global_job_queue
from .distributed.file_watcher import FileWatcher
from .distributed.scheduler import JobScheduler
from .distributed.workers import Worker
from .metrics.tracker import MetricsTracker
from .studio.engine import StudioEngine
from .studio.logs import LogBuffer, log_event
from .studio.canvas import build_canvas_manifest
from .studio.inspectors import inspect_entity
from .studio.flows import list_flows as studio_list_flows, run_flow_once
from .studio.ask import ask_studio
from .studio.ai_calls import describe_ai_call_context
from .studio.rag import list_rag_pipelines as studio_list_rag_pipelines, describe_rag_pipeline as studio_describe_rag_pipeline
from .studio.warnings import collect_warnings
from .studio.daemon import StudioDaemon
from .macros import MacroExpander, MacroExpansionRecord, default_macro_ai_callback
from .diagnostics.runner import collect_diagnostics, collect_lint, iter_ai_files
from . import linting
from .packaging.bundler import Bundler, make_server_bundle, make_worker_bundle
from .secrets.manager import SecretsManager, get_default_secrets_manager
from .plugins.registry import PluginRegistry
from .plugins.versioning import CORE_VERSION
from .optimizer.storage import OptimizerStorage
from .optimizer.overlays import OverlayStore
from .optimizer.engine import OptimizerEngine
from .optimizer.apply import SuggestionApplier
from .examples.manager import resolve_example_path, get_examples_root
from .ui.manifest import build_ui_manifest
from .flows.models import StreamEvent
from .migration.naming import migrate_source_to_naming_standard
from .memory.inspection import describe_memory_plan, describe_memory_state

BASE_DIR = Path(__file__).resolve().parents[2]
_APPLE_MARKERS = ("Canvas", "Ask Studio", "Command Palette", "Presentation")
_LEGACY_MARKER = "Minimal Developer Console"


def _is_apple_studio_dir(candidate: Path) -> bool:
    """Return True when the candidate directory contains the Apple-style Studio UI."""
    index = candidate / "index.html"
    if not index.exists():
        return False
    try:
        text = index.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    if _LEGACY_MARKER in text:
        return False
    return all(marker in text for marker in _APPLE_MARKERS)


def _resolve_studio_static_dir() -> Path | None:
    """
    Prefer the Apple-style Studio assets; bias toward the source tree when present
    to avoid stale installed copies during development, and fall back to the
    packaged assets when they look valid.
    """
    candidates: list[Path] = []
    source_dir = BASE_DIR / "src" / "namel3ss" / "studio_static"
    if source_dir.exists():
        candidates.append(source_dir)
    try:
        candidate = resources.files("namel3ss") / "studio_static"
        if candidate.is_dir():
            pkg_path = Path(candidate)
            if pkg_path not in candidates:
                candidates.append(pkg_path)
    except Exception:
        # Fall back to workspace copy below.
        pass
    valid = [candidate for candidate in candidates if _is_apple_studio_dir(candidate)]
    if valid:
        return valid[0]
    # Do not fall back to legacy/minimal consoles; we prefer to leave Studio
    # unavailable rather than serve the wrong UI.
    return None


STUDIO_STATIC_DIR = _resolve_studio_static_dir()
_STUDIO_CONFIG_FILES = ("namel3ss.config.json", "namel3ss.toml", "namel3ss.config.toml")


def _serialize_stream_event(evt: StreamEvent) -> dict[str, Any]:
    mapping: dict[str, Any] = {
        "flow": evt.get("flow"),
        "step": evt.get("step"),
        "channel": evt.get("channel"),
        "role": evt.get("role"),
        "label": evt.get("label"),
        "mode": evt.get("mode"),
    }
    kind = evt.get("kind")
    if kind == "chunk":
        mapping["event"] = "ai_chunk"
        mapping["delta"] = evt.get("delta") or ""
    elif kind == "done":
        mapping["event"] = "ai_done"
        mapping["full"] = evt.get("full") or ""
    elif kind == "error":
        mapping["event"] = "flow_error"
        mapping["error"] = evt.get("error") or ""
        if evt.get("code") is not None:
            mapping["code"] = evt.get("code")
    elif kind == "flow_done":
        mapping["event"] = "flow_done"
        mapping["success"] = bool(evt.get("success", True))
        if "result" in evt and evt.get("result") is not None:
            mapping["result"] = evt.get("result")
    elif kind == "state_change":
        mapping["event"] = "state_change"
        mapping["path"] = evt.get("path")
        if "old_value" in evt:
            mapping["old_value"] = evt.get("old_value")
        if "new_value" in evt:
            mapping["new_value"] = evt.get("new_value")
    else:
        mapping["event"] = kind or "unknown"
    return {k: v for k, v in mapping.items() if v is not None or k in {"delta", "full", "event", "old_value", "new_value"}}


class ParseRequest(BaseModel):
    source: str


class StudioFileResponse(BaseModel):
    path: str
    content: str


class StudioFileRequest(BaseModel):
    path: str = Field(..., description="Project-root-relative path to file")
    content: str


class StudioTreeNode(BaseModel):
    name: str
    path: str
    type: str  # "directory" or "file"
    kind: str | None = None
    children: list["StudioTreeNode"] | None = None


StudioTreeNode.model_rebuild()


class RunAppRequest(BaseModel):
    source: str
    app_name: str


class RunFlowRequest(BaseModel):
    source: str
    flow: str


class PagesRequest(BaseModel):
    code: str


class PageUIRequest(BaseModel):
    code: str
    page: str


class DiagnosticsRequest(BaseModel):
    paths: list[str]
    strict: bool = False
    summary_only: bool = False
    lint: bool = False


class UIManifestRequest(BaseModel):
    code: str


class UIFlowExecuteRequest(BaseModel):
    source: str | None = None
    flow: str
    args: dict[str, Any] = {}

class CodeTransformRequest(BaseModel):
    path: str
    op: str = "update_property"
    element_id: str | None = None
    parent_id: str | None = None
    position: str | None = None
    index: int | None = None
    new_element: dict[str, Any] | None = None
    property: str | None = None
    new_value: str | None = None


class UIGenerateRequest(BaseModel):
    prompt: str
    page_path: str
    selected_element_id: str | None = None


class BundleRequest(BaseModel):
    code: str
    target: str | None = "server"


class RAGQueryRequest(BaseModel):
    code: str
    query: str
    indexes: Optional[list[str]] = None


class RagStageUpdateRequest(BaseModel):
    stage: str
    changes: Dict[str, Any] = Field(default_factory=dict)


class RagPreviewRequest(BaseModel):
    query: str | None = None
    max_debug_stages: int | None = None


class FlowsRequest(BaseModel):
    code: str


class TriggerRegistrationRequest(BaseModel):
    id: str
    kind: str
    flow_name: str
    config: Dict[str, Any]
    enabled: bool = True


class TriggerFireRequest(BaseModel):
    payload: Optional[Dict[str, Any]] = None


class UIEventRequest(BaseModel):
    code: str
    page: str
    component_id: str
    event: str
    payload: Dict[str, Any] = {}


class PluginInstallRequest(BaseModel):
    path: str


class PluginMetadata(BaseModel):
    id: str
    name: str
    version: str | None = None
    description: Optional[str] = None
    author: Optional[str] = None
    compatible: Optional[bool] = True
    enabled: Optional[bool] = True
    loaded: Optional[bool] = False
    errors: List[str] = []
    path: Optional[str] = None
    entrypoints: Dict[str, Any] = {}
    contributions: Dict[str, List[str]] = {}
    tags: List[str] = []


class FmtPreviewRequest(BaseModel):
    source: str


class FmtPreviewResponse(BaseModel):
    formatted: str
    changes_made: bool


class MemoryClearRequest(BaseModel):
    kinds: List[str] | None = None


class NamingMigrationChange(BaseModel):
    from_name: str = Field(..., alias="from")
    to_name: str = Field(..., alias="to")
    model_config = ConfigDict(populate_by_name=True)


class NamingMigrationSummary(BaseModel):
    headers_rewritten: int = 0
    let_rewritten: int = 0
    set_rewritten: int = 0
    names_renamed: list[NamingMigrationChange] = []
    suggested_names: list[NamingMigrationChange] = []
    changed: bool = False


class NamingMigrationRequest(BaseModel):
    source: str
    fix_names: bool = False


class NamingMigrationResponse(BaseModel):
    source: str
    changes_summary: NamingMigrationSummary


def _parse_source_to_ast(source: str) -> Dict[str, Any]:
    tokens = lexer.Lexer(source).tokenize()
    module = parser.Parser(tokens).parse_module()
    return asdict(module)


def _parse_source_to_ir(source: str) -> ir.IRProgram:
    tokens = lexer.Lexer(source).tokenize()
    module = parser.Parser(tokens).parse_module()
    return ir.ast_to_ir(module)


def create_app(project_root: Path | None = None, daemon_state: Any | None = None) -> FastAPI:
    """Create the FastAPI app."""

    project_root = (project_root or Path.cwd()).resolve()
    app = FastAPI(title="Namel3ss V3", version="0.1.0")
    log_buffer: LogBuffer = getattr(daemon_state, "logs", LogBuffer())
    if STUDIO_STATIC_DIR and STUDIO_STATIC_DIR.exists():
        try:
            index_marker = (STUDIO_STATIC_DIR / "index.html").read_text(encoding="utf-8")
            if "Namel3ss Studio" not in index_marker:
                log_event(
                    log_buffer,
                    "studio_static_marker_missing",
                    level="warn",
                    detail=f"Resolved studio dir {STUDIO_STATIC_DIR} does not look like Apple-style Studio.",
                )
        except Exception:
            log_event(
                log_buffer,
                "studio_static_marker_read_error",
                level="warn",
                detail=f"Could not read index.html in {STUDIO_STATIC_DIR}",
            )
        app.mount(
            "/studio",
            StaticFiles(directory=str(STUDIO_STATIC_DIR), html=True),
            name="studio",
        )
        log_event(log_buffer, "static_serving_info", level="info", path=str(STUDIO_STATIC_DIR))
        @app.get("/studio-static", include_in_schema=False)
        def studio_static_redirect_root():
            return RedirectResponse(url="/studio", status_code=307)

        @app.get("/studio-static/{path:path}", include_in_schema=False)
        def studio_static_redirect(path: str):
            suffix = f"/{path}" if path else ""
            return RedirectResponse(url=f"/studio{suffix}", status_code=307)
    else:
        log_event(
            log_buffer,
            "studio_static_unavailable",
            level="error",
            detail="Apple-style Studio assets not found; UI will not be served.",
        )
    last_trace: Optional[Dict[str, Any]] = None
    recent_traces: List[Dict[str, Any]] = []
    recent_agent_traces: List[Dict[str, Any]] = []
    metrics_tracker = MetricsTracker()
    plugin_registry = PluginRegistry(
        Path(get_default_secrets_manager().get("N3_PLUGINS_DIR") or "plugins"),
        core_version=CORE_VERSION,
        tracer=Tracer(),
    )
    trigger_manager = TriggerManager(
        job_queue=global_job_queue, secrets=get_default_secrets_manager(), tracer=Tracer(), metrics=metrics_tracker, project_root=project_root
    )
    file_watcher = FileWatcher(trigger_manager, project_root)
    trigger_manager.file_watcher = file_watcher
    optimizer_storage = OptimizerStorage(Path(get_default_secrets_manager().get("N3_OPTIMIZER_DB") or "optimizer.db"))
    overlay_store = OverlayStore(Path(get_default_secrets_manager().get("N3_OPTIMIZER_OVERLAYS") or "optimizer_overlays.json"))
    state_subscribers: list[asyncio.Queue] = []

    async def _broadcast_state_event(evt: dict[str, Any]) -> None:
        if evt.get("event") != "state_change":
            return
        for subscriber in list(state_subscribers):
            try:
                await subscriber.put(evt)
            except Exception:
                try:
                    state_subscribers.remove(subscriber)
                except ValueError:
                    pass

    def _register_state_subscriber() -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        state_subscribers.append(queue)
        return queue

    def _unregister_state_subscriber(queue: asyncio.Queue) -> None:
        try:
            state_subscribers.remove(queue)
        except ValueError:
            pass

    async def _global_state_stream_callback(evt: StreamEvent) -> None:
        data = _serialize_stream_event(evt)
        await _broadcast_state_event(data)

    app.state.broadcast_state_event = _broadcast_state_event
    app.state.register_state_subscriber = _register_state_subscriber
    app.state.project_root = project_root

    def _get_cached_program() -> ir.IRProgram | None:
        if daemon_state is None:
            return None
        return getattr(daemon_state, "program", None)

    def _set_cached_program(program: ir.IRProgram | None) -> None:
        if daemon_state is None:
            return
        try:
            setattr(daemon_state, "program", program)
        except Exception:
            # Avoid blocking server startup if a custom daemon state cannot be updated.
            pass

    def _invalidate_program_cache() -> None:
        _set_cached_program(None)

    def _project_root() -> Path:
        return project_root

    def _safe_path(rel_path: str) -> Path:
        base = _project_root()
        target = (base / rel_path).resolve()
        if base not in target.parents and base != target:
            raise HTTPException(status_code=400, detail="Invalid path")
        return target

    def _file_kind(path: Path) -> str:
        parts = path.parts
        if "pages" in parts:
            return "page"
        if "flows" in parts:
            return "flow"
        if "agents" in parts:
            return "agent"
        if "forms" in parts:
            return "form"
        if "components" in parts:
            return "component"
        if "macros" in parts:
            return "macro"
        if path.name == "settings.ai":
            return "settings"
        return "file"

    @app.on_event("startup")
    async def _startup_file_watcher() -> None:  # pragma: no cover - integration
        try:
            await file_watcher.start()
        except Exception:
            pass

    @app.on_event("shutdown")
    async def _shutdown_file_watcher() -> None:  # pragma: no cover - integration
        try:
            await file_watcher.stop()
        except Exception:
            pass

    _IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}

    def _build_tree(directory: Path, base: Path) -> Optional[StudioTreeNode]:
        children: list[StudioTreeNode] = []
        for entry in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if entry.name in _IGNORED_DIRS:
                continue
            if entry.is_dir():
                child = _build_tree(entry, base)
                if child and child.children:
                    children.append(child)
                elif child and directory == base:
                    # allow empty top-level directories with no matches? skip
                    continue
            else:
                if entry.suffix != ".ai":
                    continue
                rel = entry.relative_to(base)
                children.append(
                    StudioTreeNode(
                        name=entry.name,
                        path=str(rel).replace("\\", "/"),
                        type="file",
                        kind=_file_kind(rel),
                        children=None,
                    )
                )
        rel_dir = directory.relative_to(base) if directory != base else Path(".")
        return StudioTreeNode(
            name=directory.name if directory != base else base.name,
            path=str(rel_dir).replace("\\", "/"),
            type="directory",
            kind=None,
            children=children,
        )

    def _iter_ai_files(base: Path) -> list[Path]:
        files: list[Path] = []
        for root, dirs, file_names in os.walk(base):
            dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS]
            for fname in sorted(file_names):
                if not fname.endswith(".ai"):
                    continue
                files.append(Path(root) / fname)
        return files

    def _studio_status_payload() -> Dict[str, Any]:
        base = _project_root()
        ai_files = _iter_ai_files(base)
        ai_paths = [str(p.relative_to(base)).replace("\\", "/") for p in ai_files]
        studio_static_available = bool(STUDIO_STATIC_DIR and (STUDIO_STATIC_DIR / "index.html").exists())
        config_file_found = any((base / name).exists() for name in _STUDIO_CONFIG_FILES)
        payload: Dict[str, Any] = {
            "project_root": str(base),
            "ai_files": len(ai_files),
            "ai_file_paths": ai_paths,
            "watcher_active": False,
            "watcher_supported": True,
            "ir_status": "unknown",
            "ir_error": None,
            "studio_static_available": studio_static_available,
            "config_file_found": config_file_found,
        }
        if daemon_state is not None:
            payload["watcher_active"] = bool(getattr(daemon_state, "_observer", None))
            payload["watcher_supported"] = getattr(daemon_state, "watcher_supported", True)
            cached_program = _get_cached_program()
            last_error = getattr(daemon_state, "last_error", None)
            last_error_detail = getattr(daemon_state, "last_error_detail", None)
            if cached_program:
                payload["ir_status"] = "valid"
            elif last_error:
                payload["ir_status"] = "error"
                payload["ir_error"] = last_error_detail or {"message": last_error}
            elif not ai_files:
                payload["ir_status"] = "error"
                payload["ir_error"] = {"message": "No .ai files found"}
        else:
            # Best-effort validation when running without a Studio daemon.
            payload["watcher_active"] = False
            payload["watcher_supported"] = True
            if not ai_files:
                payload["ir_status"] = "error"
                payload["ir_error"] = {"message": "No .ai files found"}
            else:
                try:
                    combined = "\n\n".join(p.read_text(encoding="utf-8") for p in ai_files)
                    Engine._load_program(combined, filename=str(base / "project.ai"))
                    payload["ir_status"] = "valid"
                except Namel3ssError as exc:
                    payload["ir_status"] = "error"
                    payload["ir_error"] = {
                        k: v
                        for k, v in {
                            "message": getattr(exc, "message", str(exc)),
                            "file": getattr(exc, "filename", None) or getattr(exc, "file", None),
                            "line": getattr(exc, "line", None),
                            "column": getattr(exc, "column", None),
                        }.items()
                        if v is not None
                    }
                except Exception as exc:
                    payload["ir_status"] = "error"
                    payload["ir_error"] = {"message": str(exc)}
                else:
                    log_event(log_buffer, "ir_reloaded", level="info", files=len(ai_files))
        return payload

    def _project_ui_manifest() -> Dict[str, Any]:
        pages: list[dict[str, Any]] = []
        components: list[dict[str, Any]] = []
        theme: dict[str, Any] = {}
        base = _project_root()
        for path in _iter_ai_files(base):
            try:
                program = Engine._load_program(path.read_text(encoding="utf-8"), filename=str(path))
                mf = build_ui_manifest(program)
            except Exception:
                continue
            if not theme and mf.get("theme"):
                theme = mf["theme"]
            existing_components = {c["name"] for c in components}
            for comp in mf.get("components", []):
                if comp["name"] not in existing_components:
                    components.append(comp)
            for page in mf.get("pages", []):
                pcopy = dict(page)
                pcopy["source_path"] = str(path.relative_to(base)).replace("\\", "/")
                def _set_source(el):
                    if isinstance(el, dict):
                        el.setdefault("source_path", pcopy["source_path"])
                        for child in el.get("layout", []):
                            _set_source(child)
                        for block in el.get("when", []):
                            _set_source(block)
                        for block in el.get("otherwise", []):
                            _set_source(block)
                    return el
                _set_source(pcopy)
                pages.append(pcopy)
        return {
            "ui_manifest_version": "1",
            "pages": pages,
            "components": components,
            "theme": theme,
        }

    def _project_program() -> ir.IRProgram:
        cached_program = _get_cached_program()
        if cached_program is not None:
            return cached_program
        base = _project_root()
        sources: list[str] = []
        for path in _iter_ai_files(base):
            sources.append(path.read_text(encoding="utf-8"))
        if not sources:
            raise HTTPException(status_code=400, detail="No .ai files found")
        combined = "\n\n".join(sources)
        try:
            program = Engine._load_program(combined, filename=str(base / "project.ai"))
            _set_cached_program(program)
            log_event(log_buffer, "ir_reloaded", level="info", files=len(sources))
            return program
        except Exception as exc:
            log_event(log_buffer, "ir_reload_error", level="error", message=str(exc))
            raise

    def _build_project_engine(program: ir.IRProgram | None = None) -> Engine:
        prog = program or _project_program()
        return Engine(
            prog,
            metrics_tracker=metrics_tracker,
            trigger_manager=trigger_manager,
            plugin_registry=plugin_registry,
        )

    def _macro_id(record: MacroExpansionRecord, idx: int) -> str:
        path_label = Path(record.source_path).name if record.source_path else "unknown"
        line = record.span.line if record.span else 0
        col = record.span.column if record.span else 0
        return f"{record.macro_name}:{path_label}:{line}:{col}:{idx}"

    def _collect_macro_invocations() -> list[tuple[str, MacroExpansionRecord]]:
        invocations: list[tuple[str, MacroExpansionRecord]] = []
        base = _project_root()
        for path in _iter_ai_files(base):
            try:
                source = path.read_text(encoding="utf-8")
                tokens = lexer.Lexer(source, filename=str(path)).tokenize()
                module = parser.Parser(tokens).parse_module()
                expander = MacroExpander(default_macro_ai_callback, capture_expansions=True)
                expander.expand_module(module, source_path=str(path))
                for rec in expander.expansion_records:
                    invocations.append((_macro_id(rec, len(invocations)), rec))
            except Exception:
                continue
        return invocations

    def _short_term_store_name(mem_cfg: Any) -> str:
        short_cfg = getattr(mem_cfg, "short_term", None)
        store = getattr(short_cfg, "store", None) if short_cfg else None
        if store:
            return store
        store = getattr(mem_cfg, "store", None)
        return store or "default_memory"

    def _long_term_store_name(mem_cfg: Any) -> str | None:
        long_cfg = getattr(mem_cfg, "long_term", None)
        return getattr(long_cfg, "store", None) if long_cfg else None

    def _profile_store_name(mem_cfg: Any) -> str | None:
        profile_cfg = getattr(mem_cfg, "profile", None)
        return getattr(profile_cfg, "store", None) if profile_cfg else None

    def _long_term_key(ai_id: str) -> str:
        return f"{ai_id}::long_term"

    def _profile_key(ai_id: str) -> str:
        return f"{ai_id}::profile"

    def _default_scope(kind: str, user_id: str | None) -> str:
        if kind == "short_term":
            return "per_session"
        if kind in {"long_term", "profile"}:
            return "per_user" if user_id else "per_session"
        return "per_session"

    def _compute_scope_keys(
        kind: str,
        cfg_scope: str | None,
        base_key: str,
        session_id: str,
        user_id: str | None,
    ) -> dict[str, Any]:
        default_scope = _default_scope(kind, user_id)
        scope = (cfg_scope or default_scope) or "per_session"
        fallback = False
        if scope == "per_user":
            if user_id:
                session_key = f"user:{user_id}"
            else:
                session_key = session_id
                scope = "per_session"
                fallback = True
        elif scope == "shared":
            session_key = "shared"
        else:
            session_key = session_id
        return {
            "ai_key": base_key,
            "session_key": session_key,
            "scope": scope,
            "fallback": fallback,
            "requested": cfg_scope or default_scope,
        }

    def _build_policy_info(
        kind: str,
        cfg: Any | None,
        scope_info: dict[str, Any] | None,
        user_id: str | None,
    ) -> dict[str, Any] | None:
        if cfg is None or scope_info is None:
            return None
        policy = {
            "scope": scope_info["scope"],
            "requested_scope": scope_info["requested"],
            "scope_fallback": scope_info["fallback"],
            "retention_days": getattr(cfg, "retention_days", None),
            "pii_policy": getattr(cfg, "pii_policy", None) or "none",
        }
        if scope_info["fallback"] and scope_info["requested"] == "per_user" and not user_id:
            policy["scope_note"] = "Using per_session fallback (no user identity)."
        return policy

    def _legacy_session_payload(ai_id: str, session_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        kinds = state.get("kinds", {})
        short_payload = kinds.get("short_term") or {}
        long_payload = kinds.get("long_term")
        profile_payload = kinds.get("profile")
        episodic_payload = kinds.get("episodic")
        semantic_payload = kinds.get("semantic")
        return {
            "ai": ai_id,
            "session": session_id,
            "user_id": state.get("user_id"),
            "short_term": {
                "window": short_payload.get("window"),
                "turns": short_payload.get("turns", []),
            },
            "long_term": (
                {"store": long_payload.get("store"), "items": long_payload.get("items", [])} if long_payload else None
            ),
            "profile": (
                {"store": profile_payload.get("store"), "facts": profile_payload.get("facts", [])}
                if profile_payload
                else None
            ),
            "episodic": episodic_payload,
            "semantic": semantic_payload,
            "policies": state.get("policies", {}),
            "last_recall_snapshot": state.get("recall_snapshot"),
            "kinds": kinds,
        }

    @app.get("/health")
    def health() -> Dict[str, str]:
        log_event(log_buffer, "health_ping", level="info")
        return {"status": "ok"}

    @app.get("/api/studio/status")
    def api_studio_status() -> Dict[str, Any]:
        try:
            payload = _studio_status_payload()
            log_event(log_buffer, "status_requested", level="info")
            return payload
        except Exception as exc:  # pragma: no cover - should never raise
            base = _project_root()
            log_event(log_buffer, "status_error", level="error", message=str(exc))
            return {
                "project_root": str(base),
                "ai_files": 0,
                "ai_file_paths": [],
                "watcher_active": False,
                "watcher_supported": False,
                "ir_status": "error",
                "ir_error": {"message": str(exc)},
                "studio_static_available": bool(STUDIO_STATIC_DIR and (STUDIO_STATIC_DIR / "index.html").exists()),
                "config_file_found": any((base / name).exists() for name in _STUDIO_CONFIG_FILES),
            }

    @app.get("/api/studio/logs/stream")
    def api_studio_logs_stream(request: Request, once: bool = False):
        # Minimal SSE-like stream using NDJSON for compatibility.
        async def event_generator():
            last_id = 0
            history = log_buffer.history()
            for entry in history:
                last_id = entry.get("id", last_id)
                yield json.dumps(entry) + "\n"
            if once:
                return
            while True:
                if await request.is_disconnected():
                    break
                events, last_id = log_buffer.snapshot_after(last_id)
                if events:
                    for entry in events:
                        yield json.dumps(entry) + "\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(event_generator(), media_type="text/plain")

    @app.get("/api/studio/canvas")
    def api_studio_canvas() -> Dict[str, Any]:
        try:
            program = _get_cached_program()
            if program is None:
                program = _project_program()
            manifest = build_canvas_manifest(program)
            return manifest
        except Exception as exc:  # pragma: no cover - defensive
            log_event(log_buffer, "canvas_error", level="error", message=str(exc))
            return {"nodes": [], "edges": [], "status": "error", "error": str(exc)}

    @app.post("/api/studio/log-note")
    def api_studio_log_note(payload: Dict[str, Any]) -> Dict[str, Any]:
        event = payload.get("event") or "note"
        level = payload.get("level") or "info"
        details = payload.get("details") or {}
        log_event(log_buffer, event, level=level, **details)
        return {"ok": True}

    @app.get("/api/studio/inspect")
    def api_studio_inspect(kind: str, name: str) -> Dict[str, Any]:
        try:
            program = _get_cached_program() or _project_program()
            entity = inspect_entity(program, kind, name)
            log_event(log_buffer, "inspector_opened", level="info", kind=kind, name=name)
            return entity
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            log_event(log_buffer, "inspector_error", level="error", kind=kind, name=name, message=str(exc))
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/studio/ask")
    def api_studio_ask(payload: Dict[str, Any]) -> Dict[str, Any]:
        question = (payload.get("question") or "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")
        mode = (payload.get("mode") or "explain").strip() or "explain"
        context_payload = payload.get("context") or {}
        status_payload = _studio_status_payload()
        entity_payload = None
        try:
            kind = context_payload.get("kind")
            name = context_payload.get("name")
            if kind and name:
                program = _get_cached_program() or _project_program()
                entity_payload = inspect_entity(program, kind, name)
        except Exception:
            entity_payload = None
        memory_payload = None
        memory_state_payload = None
        ai_id = context_payload.get("ai_id")
        session_id = context_payload.get("session_id")
        if ai_id:
            try:
                program = _project_program()
                ai_calls = getattr(program, "ai_calls", {}) or {}
                if ai_id in ai_calls:
                    memory_payload = describe_memory_plan(ai_calls[ai_id])
                    if session_id:
                        engine = _build_project_engine(program)
                        memory_state_payload = describe_memory_state(engine, ai_calls[ai_id], session_id=session_id, limit=25)
            except Exception:
                memory_payload = memory_payload or {"ai": ai_id, "error": "Unable to load memory."}
        try:
            result = ask_studio(
                question,
                status=status_payload,
                entity=entity_payload,
                logs=log_buffer.history()[-15:],
                flow_run=context_payload.get("flow_run"),
                memory=memory_payload,
                memory_state=memory_state_payload,
                mode=mode,
            )
            log_event(
                log_buffer,
                "ask_studio",
                level="info",
                question=question[:80],
                mode=mode,
                has_snippets=bool(result.get("suggested_snippets")),
            )
            return result
        except Namel3ssError as exc:
            log_event(log_buffer, "ask_studio_error", level="error", message=str(exc))
            raise HTTPException(status_code=503, detail="Ask Studio is unavailable. Check your AI provider configuration.")
        except Exception as exc:  # pragma: no cover - defensive
            log_event(log_buffer, "ask_studio_error", level="error", message=str(exc))
            raise HTTPException(status_code=503, detail="Ask Studio is unavailable. Check your AI provider configuration.")

    @app.get("/api/studio/flows")
    def api_studio_flows() -> Dict[str, Any]:
        try:
            program = _get_cached_program()
            if program is None and daemon_state is not None and getattr(daemon_state, "last_error_detail", None):
                raise HTTPException(status_code=503, detail=getattr(daemon_state, "last_error_detail"))
            program = program or _project_program()
            return {"flows": studio_list_flows(program)}
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            log_event(log_buffer, "flows_list_error", level="error", message=str(exc))
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/studio/run-flow")
    def api_studio_run_flow(payload: Dict[str, Any]) -> Dict[str, Any]:
        flow_name = (payload.get("flow") or "").strip()
        if not flow_name:
            raise HTTPException(status_code=400, detail="Missing flow name")
        state = payload.get("input") or payload.get("state") or {}
        metadata = payload.get("metadata") or {}
        try:
            program = _get_cached_program()
            if program is None and daemon_state is not None and getattr(daemon_state, "last_error_detail", None):
                raise HTTPException(status_code=503, detail=getattr(daemon_state, "last_error_detail"))
            program = program or _project_program()
            log_event(log_buffer, "flow_run_started", level="info", flow=flow_name)
            result = run_flow_once(program, flow_name, state=state, metadata=metadata)
            log_event(log_buffer, "flow_run_finished", level="info", flow=flow_name, success=result.get("success", True))
            return result
        except HTTPException:
            raise
        except KeyError:
            raise HTTPException(status_code=404, detail=f"flow '{flow_name}' not found")
        except Namel3ssError as exc:
            log_event(log_buffer, "flow_run_error", level="error", flow=flow_name, message=str(exc))
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            log_event(log_buffer, "flow_run_error", level="error", flow=flow_name, message=str(exc))
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/studio/ai-call")
    def api_studio_ai_call(ai_id: str = Query(..., alias="ai"), session_id: str = Query(..., alias="session")) -> Dict[str, Any]:
        ai_id = (ai_id or "").strip()
        session_id = (session_id or "").strip()
        if not ai_id or not session_id:
            raise HTTPException(status_code=400, detail="ai and session are required")
        try:
            program = _get_cached_program() or _project_program()
            engine = _build_project_engine(program)
            payload = describe_ai_call_context(program, ai_id, session_id, engine)
            log_event(log_buffer, "ai_call_visualized", level="info", ai=ai_id, session=session_id)
            return payload
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            log_event(log_buffer, "ai_call_visualizer_error", level="error", ai=ai_id, session=session_id, message=str(exc))
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/studio/rag/list")
    def api_studio_rag_list() -> Dict[str, Any]:
        try:
            program = _get_cached_program() or _project_program()
            pipelines = studio_list_rag_pipelines(program)
            return {"pipelines": pipelines}
        except KeyError:
            raise HTTPException(status_code=404, detail="No rag pipelines found")
        except Exception as exc:  # pragma: no cover - defensive
            log_event(log_buffer, "rag_list_error", level="error", message=str(exc))
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/studio/rag/pipeline")
    def api_studio_rag_pipeline(name: str) -> Dict[str, Any]:
        name = (name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Missing pipeline name")
        try:
            program = _get_cached_program() or _project_program()
            manifest = studio_describe_rag_pipeline(program, name)
            log_event(log_buffer, "rag_pipeline_viewed", level="info", pipeline=name)
            return manifest
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            log_event(log_buffer, "rag_pipeline_error", level="error", pipeline=name, message=str(exc))
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/studio/warnings")
    def api_studio_warnings() -> Dict[str, Any]:
        try:
            program = _get_cached_program()
            if program is None and daemon_state is not None and getattr(daemon_state, "last_error_detail", None):
                return {"warnings": []}
            program = program or _project_program()
            warnings = collect_warnings(program)
            log_event(log_buffer, "warnings_collected", level="info", count=len(warnings))
            return {"warnings": warnings}
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            log_event(log_buffer, "warnings_error", level="error", message=str(exc))
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/studio/reparse")
    def api_studio_reparse() -> Dict[str, Any]:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        errors: list[dict[str, Any]] = []
        success = False
        try:
            if isinstance(daemon_state, StudioDaemon):
                program = daemon_state.ensure_program(raise_on_error=False)
                _set_cached_program(program)
                if daemon_state.last_error_detail:
                    detail = daemon_state.last_error_detail or {}
                    if isinstance(detail, dict):
                        errors.append(detail)
                success = program is not None and not errors
            else:
                _invalidate_program_cache()
                try:
                    program = _project_program()
                    success = program is not None
                except Exception as exc:
                    detail = {"message": str(exc)}
                    errors.append(detail)
                    success = False
        except Exception as exc:  # pragma: no cover - defensive
            errors.append({"message": str(exc)})
            success = False
        log_event(log_buffer, "ir_reparse", level="info", success=success, error_count=len(errors), timestamp=timestamp)
        return {"success": success, "timestamp": timestamp, "errors": errors}

    @app.post("/api/parse")
    def api_parse(payload: ParseRequest) -> Dict[str, Any]:
        try:
            return {"ast": _parse_source_to_ast(payload.source)}
        except Exception as exc:  # pragma: no cover - FastAPI handles tracebacks
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/fmt/preview", response_model=FmtPreviewResponse)
    def api_fmt_preview(payload: FmtPreviewRequest) -> FmtPreviewResponse:
        if payload.source == "":
            return FmtPreviewResponse(formatted="", changes_made=False)
        try:
            formatted = format_source(payload.source)
        except ParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return FmtPreviewResponse(formatted=formatted, changes_made=formatted != payload.source)

    @app.post("/api/migrate/naming-standard", response_model=NamingMigrationResponse)
    def api_migrate_naming_standard(payload: NamingMigrationRequest) -> NamingMigrationResponse:
        try:
            migrated, result, summary = migrate_source_to_naming_standard(
                payload.source, apply_name_fixes=payload.fix_names
            )
        except Exception as exc:  # pragma: no cover - FastAPI handles tracebacks
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        renamed = summary.get("names_renamed") or []
        suggested = summary.get("suggested_names") or []
        return NamingMigrationResponse(
            source=migrated,
            changes_summary=NamingMigrationSummary(
                headers_rewritten=summary.get("headers_rewritten", 0),
                let_rewritten=summary.get("let_rewritten", 0),
                set_rewritten=summary.get("set_rewritten", 0),
                names_renamed=[{"from": entry["from"], "to": entry["to"]} for entry in renamed],
                suggested_names=[{"from": entry["from"], "to": entry["to"]} for entry in suggested],
                changed=summary.get("changed", False),
            ),
        )

    @app.get("/api/studio/files")
    def api_studio_files(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        root = _project_root()
        tree = _build_tree(root, root)
        if not tree:
            raise HTTPException(status_code=500, detail="Unable to scan project")
        return {"root": tree}

    @app.get("/api/studio/file", response_model=StudioFileResponse)
    def api_studio_get_file(
        path: str = Query(..., description="Project-root-relative path"), principal: Principal = Depends(get_principal)
    ) -> StudioFileResponse:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        target = _safe_path(path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        return StudioFileResponse(path=path, content=target.read_text(encoding="utf-8"))

    @app.post("/api/studio/file", response_model=StudioFileResponse)
    def api_studio_save_file(payload: StudioFileRequest, principal: Principal = Depends(get_principal)) -> StudioFileResponse:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        target = _safe_path(payload.path)
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        target.write_text(payload.content, encoding="utf-8")
        _invalidate_program_cache()
        return StudioFileResponse(path=payload.path, content=payload.content)

    def _store_trace(flow_name: Optional[str], trace_payload: Dict[str, Any], status: str, started_at: float, duration: float) -> Dict[str, Any]:
        record = {
            "id": str(uuid.uuid4()),
            "flow_name": flow_name,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at)),
            "status": status,
            "duration_seconds": duration,
            "trace": trace_payload,
        }
        recent_traces.append(record)
        while len(recent_traces) > 20:
            recent_traces.pop(0)
        return record

    def _store_agent_traces(trace_payload: Dict[str, Any], duration: float) -> None:
        pages = trace_payload.get("pages") or []
        started_at = time.time() - duration
        for page in pages:
            agents = page.get("agents") or []
            for agent in agents:
                steps = agent.get("steps") or []
                run_id = str(uuid.uuid4())
                run_record = {
                    "id": run_id,
                    "agent_name": agent.get("agent_name") or agent.get("name") or "agent",
                    "team_name": None,
                    "role": None,
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at)),
                    "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at + duration)),
                    "status": "completed",
                    "duration_seconds": duration,
                    "cost": None,
                    "token_usage": None,
                    "steps": [],
                    "messages": [],
                }
                for idx, step in enumerate(steps):
                    step_id = step.get("node_id") or f"{run_id}-step-{idx}"
                    run_record["steps"].append(
                        {
                            "id": step_id,
                            "step_name": step.get("step_name") or step.get("name") or f"step-{idx}",
                            "kind": step.get("kind") or "step",
                            "target": step.get("target"),
                            "started_at": run_record["started_at"],
                            "finished_at": run_record["finished_at"],
                            "success": step.get("success", True),
                            "retries": step.get("retries", 0),
                            "evaluation_score": step.get("evaluation_score"),
                            "evaluation_verdict": step.get("verdict"),
                            "message_preview": step.get("output_preview"),
                            "tool_calls": [],
                            "memory_events": [],
                            "rag_events": [],
                        }
                    )
                recent_agent_traces.append(run_record)
        while len(recent_agent_traces) > 50:
            recent_agent_traces.pop(0)

    @app.post("/api/run-app")
    def api_run_app(
        payload: RunAppRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_run_app(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            started_at = time.time()
            engine = Engine.from_source(
                payload.source,
                metrics_tracker=metrics_tracker,
                trigger_manager=trigger_manager,
                plugin_registry=plugin_registry,
            )
            result = engine.run_app(
                payload.app_name, include_trace=True, principal_role=principal.role.value
            )
            nonlocal last_trace
            last_trace = result.get("trace")
            duration = time.time() - started_at
            stored = _store_trace(None, last_trace, "completed", started_at, duration)
            _store_agent_traces(stored["trace"], duration)
            return {"result": result, "trace": result.get("trace")}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/example-source")
    def api_example_source(name: str) -> Dict[str, Any]:
        try:
            path = resolve_example_path(name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Example '{name}' not found")
        source = path.read_text(encoding="utf-8")
        try:
            rel_path = str(path.relative_to(get_examples_root().parent))
        except ValueError:
            rel_path = str(path)
        rel_path = rel_path.replace("\\", "/")
        return {"name": name, "path": rel_path, "source": source}

    @app.get("/studio", response_class=HTMLResponse)
    def studio() -> HTMLResponse:
        if not STUDIO_STATIC_DIR:
            log_event(log_buffer, "asset_missing_warning", level="warn", detail="studio_dir_missing")
            return HTMLResponse(
                "<html><body><h1>Studio assets not found (no static directory).</h1></body></html>",
                status_code=500,
            )
        index_path = STUDIO_STATIC_DIR / "index.html"
        if not index_path.exists():
            log_event(log_buffer, "asset_missing_warning", level="warn", detail="index_html_missing")
            return HTMLResponse(
                "<html><body><h1>Studio assets not found.</h1></body></html>",
                status_code=500,
            )
        log_event(log_buffer, "static_serving_info", level="info", path=str(index_path))
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    @app.get("/api/last-trace")
    def api_last_trace(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_traces(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        if last_trace is None:
            raise HTTPException(status_code=404, detail="No trace available")
        return {"trace": last_trace}

    @app.get("/api/traces")
    def api_traces(principal: Principal = Depends(get_principal)) -> List[Dict[str, Any]]:
        if not can_view_traces(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        summaries = []
        for rec in recent_traces:
            summaries.append(
                {
                    "id": rec["id"],
                    "flow_name": rec.get("flow_name"),
                    "started_at": rec.get("started_at"),
                    "status": rec.get("status"),
                    "duration_seconds": rec.get("duration_seconds"),
                }
            )
        return summaries

    @app.get("/api/trace/{trace_id}")
    def api_trace(trace_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_traces(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        for rec in recent_traces:
            if rec["id"] == trace_id:
                return rec
        raise HTTPException(status_code=404, detail="Trace not found")

    @app.get("/api/agent-traces")
    def api_agent_traces(principal: Principal = Depends(get_principal)) -> List[Dict[str, Any]]:
        if not can_view_traces(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        return [
            {
                "id": rec["id"],
                "agent_name": rec.get("agent_name"),
                "team_name": rec.get("team_name"),
                "role": rec.get("role"),
                "started_at": rec.get("started_at"),
                "finished_at": rec.get("finished_at"),
                "status": rec.get("status"),
                "duration_seconds": rec.get("duration_seconds"),
                "cost": rec.get("cost"),
            }
            for rec in recent_agent_traces
        ]

    @app.get("/api/agent-trace/{trace_id}")
    def api_agent_trace(trace_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_traces(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        for rec in recent_agent_traces:
            if rec["id"] == trace_id:
                return rec
        raise HTTPException(status_code=404, detail="Agent trace not found")

    @app.post("/api/run-flow")
    def api_run_flow(
        payload: RunFlowRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            started_at = time.time()
            engine = Engine.from_source(
                payload.source,
                metrics_tracker=metrics_tracker,
                trigger_manager=trigger_manager,
                plugin_registry=plugin_registry,
            )
            result = engine.execute_flow(
                payload.flow, principal_role=principal.role.value
            )
            nonlocal last_trace
            last_trace = result.get("trace")
            duration = time.time() - started_at
            stored = _store_trace(payload.flow, last_trace, "completed", started_at, duration)
            _store_agent_traces(stored["trace"], duration)
            return {"result": result, "trace": result.get("trace")}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/pages")
    def api_pages(
        payload: PagesRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            module = parser.Parser(lexer.Lexer(payload.code).tokenize()).parse_module()
            program = ir.ast_to_ir(module)
            pages = [
                {"name": page.name, "route": page.route, "title": page.title}
                for page in program.pages.values()
            ]
            return {"pages": pages}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/page-ui")
    def api_page_ui(
        payload: PageUIRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = Engine.from_source(payload.code, trigger_manager=trigger_manager, plugin_registry=plugin_registry)
            if payload.page not in engine.program.pages:
                raise HTTPException(status_code=404, detail="Page not found")
            ui_page = engine.ui_renderer.from_ir_page(engine.program.pages[payload.page])
            runtime_components = engine.ui_renderer.build_runtime_components(engine.program.pages[payload.page])
            return {"ui": ui_page.__dict__, "components": [c.__dict__ for c in runtime_components]}
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/ui/manifest")
    def api_ui_manifest_current(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            return _project_ui_manifest()
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/ui/flow/info")
    def api_ui_flow_info(name: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            program = _project_program()
            if name not in program.flows:
                raise HTTPException(status_code=404, detail="Flow not found")
            return {"name": name, "args": {}, "returns": "any"}
        except HTTPException as exc:
            if exc.status_code == 400:
                raise HTTPException(status_code=404, detail=exc.detail)
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ui/manifest")
    def api_ui_manifest(payload: UIManifestRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = Engine.from_source(payload.code, trigger_manager=trigger_manager, plugin_registry=plugin_registry)
            manifest = build_ui_manifest(engine.program)
            return manifest
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/ui/state/stream")
    async def api_ui_state_stream(principal: Principal = Depends(get_principal)):
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        queue = _register_state_subscriber()

        async def event_stream():
            try:
                while True:
                    item = await queue.get()
                    yield json.dumps(item) + "\n"
            finally:
                _unregister_state_subscriber(queue)

        return StreamingResponse(event_stream(), media_type="application/json")

    @app.post("/api/ui/flow/execute")
    def api_ui_flow_execute(payload: UIFlowExecuteRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            if payload.source:
                engine = Engine.from_source(
                    payload.source,
                    metrics_tracker=metrics_tracker,
                    trigger_manager=trigger_manager,
                    plugin_registry=plugin_registry,
                )
            else:
                program = _project_program()
                engine = Engine(
                    program,
                    metrics_tracker=metrics_tracker,
                    trigger_manager=trigger_manager,
                    plugin_registry=plugin_registry,
                )
            engine.flow_engine.global_stream_callback = _global_state_stream_callback
            result = engine.execute_flow(payload.flow, principal_role=principal.role.value, payload={"state": payload.args})
            return {"success": True, "result": result}
        except Exception as exc:  # pragma: no cover
            return {"success": False, "error": str(exc)}

    @app.post("/api/ui/flow/stream")
    async def api_ui_flow_stream(payload: UIFlowExecuteRequest, principal: Principal = Depends(get_principal)):
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            if payload.source:
                engine = Engine.from_source(
                    payload.source,
                    metrics_tracker=metrics_tracker,
                    trigger_manager=trigger_manager,
                    plugin_registry=plugin_registry,
                )
            else:
                program = _project_program()
                engine = Engine(
                    program,
                    metrics_tracker=metrics_tracker,
                    trigger_manager=trigger_manager,
                    plugin_registry=plugin_registry,
                )
            engine.flow_engine.global_stream_callback = _global_state_stream_callback
            if payload.flow not in engine.program.flows:
                raise HTTPException(status_code=404, detail="Flow not found")
            flow = engine.program.flows[payload.flow]
            context = ExecutionContext(
                app_name="__flow__",
                request_id=str(uuid.uuid4()),
                memory_engine=engine.memory_engine,
                memory_stores=engine.memory_stores,
                rag_engine=engine.rag_engine,
                tracer=Tracer(),
                tool_registry=engine.tool_registry,
                metrics=metrics_tracker,
                secrets=engine.secrets_manager,
                trigger_manager=engine.trigger_manager,
            )
            initial_state = payload.args or {}

            queue: asyncio.Queue = asyncio.Queue()

            async def emit(event: StreamEvent):
                serialized = _serialize_stream_event(event)
                await queue.put(serialized)
                await _broadcast_state_event(serialized)

            async def runner():
                try:
                    result = await engine.flow_engine.run_flow_async(
                        flow, context, initial_state=initial_state, stream_callback=emit
                    )
                    if result.errors:
                        err = result.errors[0]
                        await emit(
                            {
                                "kind": "error",
                                "flow": flow.name,
                                "step": err.node_id or err.error,
                                "error": err.error,
                            }
                        )
                    else:
                        serialized_result = result.to_dict() if hasattr(result, "to_dict") else asdict(result)
                        await emit(
                            {
                                "kind": "flow_done",
                                "flow": flow.name,
                                "step": flow.steps[-1].name if flow.steps else flow.name,
                                "success": True,
                                "result": serialized_result,
                            }
                        )
                except Exception as exc:  # pragma: no cover
                    await emit({"kind": "error", "flow": flow.name, "step": flow.name, "error": str(exc)})
                finally:
                    await queue.put(None)

            asyncio.create_task(runner())

            async def event_stream():
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield json.dumps(item) + "\n"

            return StreamingResponse(event_stream(), media_type="application/json")
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/memory/ai/{ai_id}/plan")
    def api_memory_plan(ai_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        program = _project_program()
        ai_calls = getattr(program, "ai_calls", {})
        if ai_id not in ai_calls:
            raise HTTPException(status_code=404, detail="AI not found")
        plan = describe_memory_plan(ai_calls[ai_id])
        return plan

    @app.get("/api/memory/ai/{ai_id}/state")
    def api_memory_state(
        ai_id: str,
        session_id: str | None = Query(default=None),
        user_id: str | None = Query(default=None),
        limit: int = Query(default=25, ge=1, le=200),
        principal: Principal = Depends(get_principal),
    ) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        if not session_id and not user_id:
            raise HTTPException(status_code=400, detail="Provide session_id or user_id to inspect memory.")
        program = _project_program()
        ai_calls = getattr(program, "ai_calls", {})
        if ai_id not in ai_calls:
            raise HTTPException(status_code=404, detail="AI not found")
        engine = _build_project_engine(program)
        try:
            state = describe_memory_state(engine, ai_calls[ai_id], session_id=session_id, user_id=user_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return state

    @app.get("/api/memory/ai/{ai_id}/sessions")
    def api_memory_sessions(ai_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        program = _project_program()
        ai_calls = getattr(program, "ai_calls", {})
        if ai_id not in ai_calls:
            raise HTTPException(status_code=404, detail="AI not found")
        ai_call = ai_calls[ai_id]
        mem_cfg = getattr(ai_call, "memory", None)
        if not mem_cfg:
            return {"ai": ai_id, "sessions": []}
        engine = _build_project_engine(program)
        store_name = _short_term_store_name(mem_cfg)
        backend = engine.memory_stores.get(store_name)
        if backend is None:
            raise HTTPException(status_code=404, detail=f"Memory store '{store_name}' unavailable")
        sessions = backend.list_sessions(ai_id)
        serialized = [
            {
                "id": entry.get("id"),
                "last_activity": entry.get("last_activity"),
                "turns": entry.get("turns", 0),
                "user_id": entry.get("user_id"),
            }
            for entry in sessions
        ]
        return {"ai": ai_id, "sessions": serialized}

    @app.get("/api/memory/ai/{ai_id}/sessions/{session_id}")
    def api_memory_session_detail(
        ai_id: str, session_id: str, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        program = _project_program()
        ai_calls = getattr(program, "ai_calls", {})
        if ai_id not in ai_calls:
            raise HTTPException(status_code=404, detail="AI not found")
        ai_call = ai_calls[ai_id]
        mem_cfg = getattr(ai_call, "memory", None)
        if not mem_cfg:
            return {"ai": ai_id, "session": session_id, "short_term": {"turns": []}}
        engine = _build_project_engine(program)
        try:
            state = describe_memory_state(engine, ai_call, session_id=session_id, limit=50)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return _legacy_session_payload(ai_id, session_id, state)

    @app.post("/api/memory/ai/{ai_id}/sessions/{session_id}/clear")
    def api_memory_session_clear(
        ai_id: str,
        session_id: str,
        payload: MemoryClearRequest,
        principal: Principal = Depends(get_principal),
    ) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        program = _project_program()
        ai_calls = getattr(program, "ai_calls", {})
        if ai_id not in ai_calls:
            raise HTTPException(status_code=404, detail="AI not found")
        mem_cfg = getattr(ai_calls[ai_id], "memory", None)
        if not mem_cfg:
            return {"success": True}
        engine = _build_project_engine(program)
        memory_stores = engine.memory_stores
        kinds = payload.kinds or ["short_term", "long_term", "profile"]
        short_cfg = getattr(mem_cfg, "short_term", None)
        if short_cfg is None and (getattr(mem_cfg, "kind", None) or getattr(mem_cfg, "window", None) or getattr(mem_cfg, "store", None)):
            short_cfg = ir.IRAiShortTermMemoryConfig(window=getattr(mem_cfg, "window", None), store=getattr(mem_cfg, "store", None))
        short_store_name = _short_term_store_name(mem_cfg)
        short_backend = memory_stores.get(short_store_name)
        session_user_id: str | None = None
        if short_backend and hasattr(short_backend, "get_session_user"):
            try:
                session_user_id = short_backend.get_session_user(ai_id, session_id)
            except Exception:
                session_user_id = None
        short_scope = _compute_scope_keys(
            "short_term",
            getattr(short_cfg, "scope", None) if short_cfg else None,
            ai_id,
            session_id,
            session_user_id,
        )
        if "short_term" in kinds and short_store_name in memory_stores:
            memory_stores[short_store_name].clear_session(short_scope["ai_key"], short_scope["session_key"])
        long_cfg = getattr(mem_cfg, "long_term", None)
        long_scope = (
            _compute_scope_keys("long_term", getattr(long_cfg, "scope", None), _long_term_key(ai_id), session_id, session_user_id)
            if long_cfg
            else None
        )
        long_store_name = _long_term_store_name(mem_cfg)
        if (
            "long_term" in kinds
            and long_scope
            and long_store_name
            and long_store_name in memory_stores
        ):
            memory_stores[long_store_name].clear_session(long_scope["ai_key"], long_scope["session_key"])
        profile_cfg = getattr(mem_cfg, "profile", None)
        profile_scope = (
            _compute_scope_keys("profile", getattr(profile_cfg, "scope", None), _profile_key(ai_id), session_id, session_user_id)
            if profile_cfg
            else None
        )
        profile_store_name = _profile_store_name(mem_cfg)
        if (
            "profile" in kinds
            and profile_scope
            and profile_store_name
            and profile_store_name in memory_stores
        ):
            memory_stores[profile_store_name].clear_session(profile_scope["ai_key"], profile_scope["session_key"])
        clear_recall_snapshot(ai_id, session_id)
        return {"success": True}

    @app.get("/api/memory/ais")
    def api_memory_ai_list(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        program = _project_program()
        ai_calls = getattr(program, "ai_calls", {}) or {}
        ais: list[dict[str, Any]] = []
        for name, ai_call in ai_calls.items():
            if getattr(ai_call, "memory", None) or getattr(ai_call, "memory_name", None):
                ais.append({"id": name, "name": name, "has_memory": True})
        return {"ais": ais}

    def _find_element_by_id(pages: list[dict[str, Any]], element_id: str) -> dict[str, Any] | None:
        for page in pages:
            stack = list(page.get("layout", []))
            while stack:
                el = stack.pop()
                if isinstance(el, dict) and el.get("id") == element_id:
                    el["page"] = page.get("name")
                    el["page_route"] = page.get("route")
                    el["source_path"] = el.get("source_path") or page.get("source_path")
                    return el
                if isinstance(el, dict):
                    stack.extend(el.get("layout", []))
                    stack.extend(el.get("when", []))
                    stack.extend(el.get("otherwise", []))
        return None

    def _replace_string_value(text: str, old: str, new: str) -> str:
        target = f'"{old}"'
        replacement = f'"{new}"'
        if target not in text:
            return text
        return text.replace(target, replacement, 1)

    def _element_pattern(el: dict[str, Any]) -> str | None:
        t = el.get("type")
        if t == "heading":
            return f'heading "{el.get("text", "")}"'
        if t == "text":
            return f'text "{el.get("text", "")}"'
        if t == "button":
            return f'button "{el.get("label", "")}"'
        if t == "input":
            return f'input "{el.get("label", "")}'
        if t == "section":
            return f'section "{el.get("name", "")}"'
        return None

    def _find_line_index(lines: list[str], target_el: dict[str, Any]) -> int:
        pattern = _element_pattern(target_el)
        if not pattern:
            return -1
        for idx, line in enumerate(lines):
            if pattern in line.strip():
                return idx
        return -1

    def _render_new_element(data: dict[str, Any], indent: str) -> str:
        t = data.get("type")
        if t == "heading":
            return f'{indent}heading "{data.get("properties", {}).get("label", "New heading")}"'
        if t == "text":
            return f'{indent}text "{data.get("properties", {}).get("text", "New text")}"'
        if t == "button":
            return f'{indent}button "{data.get("properties", {}).get("label", "New button")}"'
        if t == "input":
            label = data.get("properties", {}).get("label", "New field")
            return f'{indent}input "{label}" as field'
        if t == "section":
            name = data.get("properties", {}).get("label", "Section")
            return f'{indent}section "{name}":'
        return f"{indent}text \"New\""

    @app.post("/api/studio/code/transform")
    def api_code_transform(payload: CodeTransformRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        base = _project_root()
        target = (base / payload.path).resolve()
        if base not in target.parents and base != target:
            raise HTTPException(status_code=400, detail="Invalid path")
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        manifest = _project_ui_manifest()
        el = None
        if payload.element_id:
            el = _find_element_by_id(manifest.get("pages", []), payload.element_id)
        try:
            content = target.read_text(encoding="utf-8")
            op = payload.op or "update_property"
            new_element_id = None
            if op == "update_property":
                if not el:
                    raise HTTPException(status_code=404, detail="Element not found")
                prop = payload.property
                if prop in ("label", "text"):
                    old_val = el.get("label") or el.get("text") or ""
                    content = _replace_string_value(content, old_val, payload.new_value or "")
                elif prop == "color":
                    old_val = None
                    for s in el.get("styles", []):
                        if s.get("kind") == "color":
                            old_val = s.get("value")
                    if old_val is None:
                        raise HTTPException(status_code=400, detail="Property not found")
                    content = content.replace(str(old_val), payload.new_value or "", 1)
                elif prop == "layout":
                    old_layout = None
                    for s in el.get("styles", []):
                        if s.get("kind") == "layout":
                            old_layout = s.get("value")
                    if old_layout:
                        content = content.replace(f"layout is {old_layout}", f"layout is {payload.new_value}", 1)
                    else:
                        raise HTTPException(status_code=400, detail="Property not found")
                else:
                    raise HTTPException(status_code=400, detail="Unsupported property")
            elif op in {"insert_element", "delete_element", "move_element"}:
                lines = content.splitlines()
                indent_unit = "  "

                def find_line_for_element(target_el: dict[str, Any]) -> int:
                    pattern = _element_pattern(target_el)
                    if not pattern:
                        return -1
                    for idx, line in enumerate(lines):
                        if pattern in line.strip():
                            return idx
                    return -1

                if op == "insert_element":
                    parent_id = payload.parent_id or (el and el.get("parent_id"))
                    position = payload.position or "after"
                    template = _render_new_element(payload.new_element or {}, indent_unit)
                    insert_at = len(lines)
                    if el and position in {"before", "after"}:
                        idx = find_line_for_element(el)
                        if idx >= 0:
                            insert_at = idx + (1 if position == "after" else 0)
                    if insert_at > len(lines):
                        lines.append(template)
                    else:
                        lines.insert(insert_at, template)
                    new_element_id = "pending"
                elif op == "delete_element":
                    if not el:
                        raise HTTPException(status_code=404, detail="Element not found")
                    idx = find_line_for_element(el)
                    if idx >= 0:
                        del lines[idx]
                    else:
                        raise HTTPException(status_code=400, detail="Cannot locate element")
                elif op == "move_element":
                    direction = payload.position or "after"
                    if not el:
                        raise HTTPException(status_code=404, detail="Element not found")
                    idx = find_line_for_element(el)
                    if idx < 0:
                        raise HTTPException(status_code=400, detail="Cannot locate element")
                    if direction == "up" and idx > 0:
                        lines[idx - 1], lines[idx] = lines[idx], lines[idx - 1]
                    elif direction == "down" and idx < len(lines) - 1:
                        lines[idx + 1], lines[idx] = lines[idx], lines[idx + 1]
                content = "\n".join(lines) + ("\n" if content.endswith("\n") else "")
            else:
                raise HTTPException(status_code=400, detail="Unsupported operation")
            target.write_text(content, encoding="utf-8")
            _invalidate_program_cache()
            manifest = _project_ui_manifest()
            return {"success": True, "manifest": manifest, "new_element_id": new_element_id}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/studio/ui/generate")
    def api_ui_generate(payload: UIGenerateRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        base = _project_root()
        target = (base / payload.page_path).resolve()
        if base not in target.parents and base != target:
            raise HTTPException(status_code=400, detail="Invalid path")
        if not target.exists():
            raise HTTPException(status_code=404, detail="File not found")
        manifest = _project_ui_manifest()
        selected_el = None
        if payload.selected_element_id:
            selected_el = _find_element_by_id(manifest.get("pages", []), payload.selected_element_id)
            if selected_el is None:
                raise HTTPException(status_code=404, detail="Element not found")
        try:
            content = target.read_text(encoding="utf-8")
            lines = content.splitlines()
            indent_unit = "  "
            insert_idx = len(lines)
            insert_indent = indent_unit
            if selected_el:
                idx = _find_line_index(lines, selected_el)
                if idx >= 0:
                    line = lines[idx]
                    leading = len(line) - len(line.lstrip(" "))
                    insert_indent = line[:leading]
                    insert_idx = idx + 1
                    if selected_el.get("type") == "section":
                        insert_indent = insert_indent + indent_unit
            prompt_text = payload.prompt.strip()
            if not prompt_text:
                prompt_text = "Generated UI"
            snippet = [
                f'{insert_indent}heading "AI Generated"',
                f'{insert_indent}text "{prompt_text[:60]}"',
            ]
            lines[insert_idx:insert_idx] = snippet
            content_out = "\n".join(lines) + ("\n" if content.endswith("\n") else "")
            target.write_text(content_out, encoding="utf-8")
            _invalidate_program_cache()
            manifest = _project_ui_manifest()
            return {"success": True, "manifest": manifest}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/flows")
    def api_flows(
        payload: FlowsRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            program = _parse_source_to_ir(payload.code)
            flows = [
                {"name": flow.name, "description": flow.description, "steps": len(flow.steps)}
                for flow in program.flows.values()
            ]
            return {"flows": flows}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/diagnostics")
    def api_diagnostics(payload: DiagnosticsRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            paths = [Path(p) for p in payload.paths]
            ai_files = iter_ai_files(paths)
            diags, summary = collect_diagnostics(ai_files, payload.strict)
            lint_results: list[dict[str, Any]] = []
            if payload.lint:
                lint_results = [d.to_dict() for d in collect_lint(ai_files, config=linting.LintConfig.load(project_root))]
            success = summary["errors"] == 0
            return {
                "success": success,
                "diagnostics": [] if payload.summary_only else [d.to_dict() for d in diags],
                "lint": [] if payload.summary_only else lint_results,
                "summary": summary,
            }
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/bundle")
    def api_bundle(
        payload: BundleRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            ir_program = _parse_source_to_ir(payload.code)
            bundler = Bundler()
            bundle = bundler.from_ir(ir_program)
            target = (payload.target or "server").lower()
            if target == "worker":
                return {"bundle": make_worker_bundle(bundle)}
            return {"bundle": make_server_bundle(bundle)}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/providers/status")
    def api_providers_status(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        cfg = load_config()
        providers_cfg = cfg.providers_config or ProvidersConfig()
        providers: list[dict[str, Any]] = []
        for name, pcfg in (providers_cfg.providers or {}).items():
            env_key = pcfg.api_key_env
            resolved = pcfg.api_key or (env_key and os.environ.get(env_key))
            if not resolved and pcfg.type == "openai":
                resolved = os.environ.get("N3_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
            if not resolved and pcfg.type == "gemini":
                resolved = os.environ.get("N3_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if not resolved and pcfg.type == "anthropic":
                resolved = os.environ.get("N3_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
            has_key = bool(resolved)
            status = ModelRegistry.last_status.get(name, "ok" if has_key else "missing_key")
            providers.append(
                {
                    "name": name,
                    "type": pcfg.type,
                    "has_key": has_key,
                    "last_check_status": status,
                }
            )
        return {"default": providers_cfg.default, "providers": providers}

    @app.get("/api/meta")
    def api_meta(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = Engine.from_source(
            "", metrics_tracker=metrics_tracker, trigger_manager=trigger_manager, plugin_registry=plugin_registry
        )
        return {
            "ai": {
                "models": list(engine.registry.models.keys()),
                "providers": list(engine.registry.providers.keys()),
                "config": engine.router.config.__dict__,
            },
            "plugins": [
                {"name": p.name, "enabled": p.enabled, "description": p.description}
                for p in engine.plugin_registry.list_plugins()
            ],
            "security": {
                "roles": [r.value for r in Role],
                "auth": f"{API_KEY_HEADER} header required",
            },
        }

    scheduler = JobScheduler(global_job_queue)
    worker = Worker(
        runtime_factory=lambda code: Engine.from_source(
            code or "",
            metrics_tracker=metrics_tracker,
            trigger_manager=trigger_manager,
            plugin_registry=plugin_registry,
        ),
        job_queue=global_job_queue,
        tracer=Tracer(),
    )

    @app.post("/api/job/flow")
    def api_job_flow(
        payload: RunFlowRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        job = scheduler.schedule_flow(payload.flow, {"code": payload.source})
        return {"job_id": job.id}

    @app.get("/api/job/{job_id}")
    def api_job_status(job_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        job = global_job_queue.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"job": job.__dict__}

    @app.post("/api/worker/run-once")
    async def api_worker_run_once(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        job = await worker.run_once()
        return {"processed": job.id if job else None}

    @app.get("/api/metrics")
    def api_metrics(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"metrics": metrics_tracker.snapshot()}

    @app.post("/api/rag/query")
    async def api_rag_query(
        payload: RAGQueryRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = Engine.from_source(
                payload.code, metrics_tracker=metrics_tracker, trigger_manager=trigger_manager, plugin_registry=plugin_registry
            )
            results = await engine.rag_engine.a_retrieve(payload.query, index_names=payload.indexes)
            if engine.rag_engine.tracer:
                engine.rag_engine.tracer.update_last_rag_result_count(len(results))
            return {
                "results": [
                    {
                        "text": r.item.text,
                        "score": r.score,
                        "source": r.source,
                        "metadata": r.item.metadata,
                    }
                    for r in results
                ]
            }
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/rag/upload")
    async def api_rag_upload(
        file: UploadFile = File(...),
        index: str = Form("default"),
        principal: Principal = Depends(get_principal),
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            content_bytes = await file.read()
            try:
                text = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = content_bytes.decode("latin-1", errors="ignore")
            engine = Engine.from_source(
                "", metrics_tracker=metrics_tracker, trigger_manager=trigger_manager, plugin_registry=plugin_registry
            )
            await engine.rag_engine.a_index_documents(index, [text])
            return {"indexed": 1, "index": index}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/flows/triggers")
    async def api_list_triggers(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        triggers = await trigger_manager.a_list_triggers()
        return {
            "triggers": [
                {
                    "id": t.id,
                    "kind": t.kind,
                    "flow_name": t.flow_name,
                    "config": t.config,
                    "enabled": t.enabled,
                    "last_fired": t.last_fired.isoformat() if t.last_fired else None,
                    "next_fire_at": t.next_fire_at.isoformat() if t.next_fire_at else None,
                }
                for t in triggers
            ]
        }

    @app.post("/api/flows/triggers")
    async def api_register_trigger(
        payload: TriggerRegistrationRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        trigger = FlowTrigger(
            id=payload.id,
            kind=payload.kind,
            flow_name=payload.flow_name,
            config=payload.config,
            enabled=payload.enabled,
        )
        await trigger_manager.a_register_trigger(trigger)
        return {"trigger": trigger.__dict__}

    @app.post("/api/flows/trigger/{trigger_id}")
    async def api_fire_trigger(
        trigger_id: str, payload: TriggerFireRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        job = await trigger_manager.a_fire_trigger(trigger_id, payload.payload or {})
        return {"job_id": job.id if job else None}

    @app.post("/api/flows/triggers/tick")
    async def api_tick_triggers(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        fired = await trigger_manager.a_tick_schedules()
        return {"fired": [job.id for job in fired]}

    @app.get("/api/plugins")
    def api_plugins(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        manifests = {m.id or m.name: m for m in plugin_registry.list_plugins()}
        plugins: List[PluginMetadata] = []
        for info in plugin_registry.discover():
            manifest = manifests.get(info.id)
            tags = manifest.tags if manifest else []
            plugins.append(
                PluginMetadata(
                    id=info.id,
                    name=info.name,
                    version=info.version,
                    description=info.description,
                    author=info.author,
                    compatible=info.compatible,
                    enabled=info.enabled,
                    loaded=info.loaded,
                    errors=info.errors,
                    path=info.path,
                    entrypoints=info.entrypoints,
                    contributions=info.contributions,
                    tags=tags or [],
                )
            )
        return {"plugins": [p.model_dump() for p in plugins]}

    @app.post("/api/plugins/{plugin_id}/load")
    def api_plugin_load(plugin_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        # build sdk from a minimal engine so plugin can register contributions
        engine = Engine.from_source(
            "", metrics_tracker=metrics_tracker, trigger_manager=trigger_manager, plugin_registry=plugin_registry
        )
        from .plugins.sdk import PluginSDK

        sdk = PluginSDK.from_engine(engine)
        info = plugin_registry.load(plugin_id, sdk)
        return {"plugin": info.__dict__}

    @app.post("/api/plugins/{plugin_id}/unload")
    def api_plugin_unload(plugin_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = Engine.from_source(
            "", metrics_tracker=metrics_tracker, trigger_manager=trigger_manager, plugin_registry=plugin_registry
        )
        from .plugins.sdk import PluginSDK

        sdk = PluginSDK.from_engine(engine)
        plugin_registry.unload(plugin_id, sdk)
        return {"status": "ok"}

    @app.post("/api/plugins/install")
    def api_plugin_install(
        payload: PluginInstallRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        path = Path(payload.path)
        info = plugin_registry.install_from_path(path)
        return {"plugin": info.__dict__}

    @app.get("/api/jobs")
    def api_jobs(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"jobs": [job.__dict__ for job in global_job_queue.list()]}

    @app.post("/api/ui/event")
    async def api_ui_event(
        payload: UIEventRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = Engine.from_source(
                payload.code, metrics_tracker=metrics_tracker, trigger_manager=trigger_manager, plugin_registry=plugin_registry
            )
            if payload.page not in engine.program.pages:
                raise HTTPException(status_code=404, detail="Page not found")
            router = UIEventRouter(
                flow_engine=engine.flow_engine,
                agent_runner=engine.agent_runner,
                tool_registry=engine.tool_registry,
                rag_engine=engine.rag_engine,
                job_queue=engine.job_queue,
                memory_engine=engine.memory_engine,
                tracer=metrics_tracker and Tracer(),
                metrics=metrics_tracker,
            )
            components = engine.ui_renderer.build_runtime_components(engine.program.pages[payload.page])
            target_comp = next((c for c in components if c.id == payload.component_id), None)
            if not target_comp:
                raise HTTPException(status_code=404, detail="Component not found")
            ui_context = UIContext(
                app_name=engine.program.apps[list(engine.program.apps.keys())[0]].name if engine.program.apps else "__app__",
                page_name=payload.page,
                metadata={"execution_context": engine._build_default_execution_context()},
            )
            event = UIEvent(component_id=payload.component_id, event=payload.event, payload=payload.payload)
            result = await router.a_handle_event(target_comp, event, ui_context)
            return {"result": result.__dict__}
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/optimizer/suggestions")
    def api_optimizer_suggestions(
        status: Optional[str] = None, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        storage = optimizer_storage
        from namel3ss.optimizer.models import OptimizationStatus

        stat = OptimizationStatus(status) if status else None
        suggestions = storage.list(stat)
        return {"suggestions": [s.__dict__ for s in suggestions]}

    @app.post("/api/optimizer/scan")
    def api_optimizer_scan(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = OptimizerEngine(
            storage=optimizer_storage,
            metrics=metrics_tracker,
            memory_engine=None,
            tracer=Tracer(),
            router=None,
            secrets=get_default_secrets_manager(),
        )
        suggestions = engine.scan()
        return {"created": [s.id for s in suggestions]}

    @app.post("/api/optimizer/apply/{suggestion_id}")
    def api_optimizer_apply(suggestion_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        sugg = optimizer_storage.get(suggestion_id)
        if not sugg:
            raise HTTPException(status_code=404, detail="Not found")
        applier = SuggestionApplier(overlay_store, optimizer_storage, tracer=Tracer())
        applier.apply(sugg)
        return {"status": "applied"}

    @app.post("/api/optimizer/reject/{suggestion_id}")
    def api_optimizer_reject(suggestion_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        sugg = optimizer_storage.get(suggestion_id)
        if not sugg:
            raise HTTPException(status_code=404, detail="Not found")
        from namel3ss.optimizer.models import OptimizationStatus

        sugg.status = OptimizationStatus.REJECTED
        optimizer_storage.update(sugg)
        return {"status": "rejected"}

    @app.get("/api/optimizer/overlays")
    def api_optimizer_overlays(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"overlays": overlay_store.load().to_dict()}

    @app.get("/api/studio-summary")
    def api_studio_summary(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = _build_project_engine()
        except HTTPException:
            engine = Engine.from_source(
                "", metrics_tracker=metrics_tracker, trigger_manager=trigger_manager, plugin_registry=plugin_registry
            )
        except Exception:
            engine = Engine.from_source(
                "", metrics_tracker=metrics_tracker, trigger_manager=trigger_manager, plugin_registry=plugin_registry
            )
        studio = StudioEngine(
            job_queue=global_job_queue,
            tracer=Tracer(),
            metrics_tracker=metrics_tracker,
            memory_engine=engine.memory_engine,
            rag_engine=engine.rag_engine,
            ir_program=engine.program,
            plugin_registry=engine.plugin_registry,
        )
        summary = studio.build_summary()
        return {"summary": summary.__dict__}

    # ---------- Studio RAG pipeline endpoints ----------
    def _serialize_rag_stage(stage, idx: int | None = None) -> Dict[str, Any]:
        data = {
            "name": getattr(stage, "name", ""),
            "type": getattr(stage, "type", ""),
            "ai": getattr(stage, "ai", None),
            "vector_store": getattr(stage, "vector_store", None),
            "graph": getattr(stage, "graph", None),
            "graph_summary": getattr(stage, "graph_summary", None),
            "frame": getattr(stage, "frame", None),
            "top_k": getattr(stage, "top_k", None),
            "max_rows": getattr(stage, "max_rows", None),
            "group_by": getattr(stage, "group_by", None),
            "max_rows_per_group": getattr(stage, "max_rows_per_group", None),
            "max_items": getattr(stage, "max_items", None),
            "strategy": getattr(stage, "strategy", None),
            "max_hops": getattr(stage, "max_hops", None),
            "max_nodes": getattr(stage, "max_nodes", None),
        }
        if idx is not None:
            data["index"] = idx
        return data

    def _serialize_rag_pipeline(pipeline) -> Dict[str, Any]:
        stages = [_serialize_rag_stage(st, idx) for idx, st in enumerate(getattr(pipeline, "stages", []))]
        edges = []
        for idx, st in enumerate(stages):
            if idx + 1 < len(stages):
                edges.append({"from": stages[idx]["name"], "to": stages[idx + 1]["name"]})
        return {
            "name": getattr(pipeline, "name", ""),
            "default_vector_store": getattr(pipeline, "default_vector_store", None),
            "stages": stages,
            "edges": edges,
        }

    @app.get("/api/studio/rag/pipelines")
    def api_studio_rag_pipelines(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = _build_project_engine()
        except Exception:
            engine = Engine.from_source(
                "", metrics_tracker=metrics_tracker, trigger_manager=trigger_manager, plugin_registry=plugin_registry
            )
        pipelines = [
            {"id": name, "name": name, "description": "", "source": None}
            for name in (getattr(engine.program, "rag_pipelines", {}) or {}).keys()
        ]
        return {"pipelines": pipelines}

    @app.get("/api/studio/rag/pipelines/{pipeline_id}")
    def api_studio_rag_pipeline_detail(pipeline_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = _build_project_engine()
        pipeline = (getattr(engine.program, "rag_pipelines", {}) or {}).get(pipeline_id)
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        return {"pipeline": _serialize_rag_pipeline(pipeline)}

    @app.post("/api/studio/rag/pipelines/{pipeline_id}/update_stage")
    def api_studio_rag_update_stage(
        pipeline_id: str, payload: RagStageUpdateRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = _build_project_engine()
        pipeline = (getattr(engine.program, "rag_pipelines", {}) or {}).get(pipeline_id)
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        stage_name = payload.stage
        changes = payload.changes or {}
        stage = next((st for st in pipeline.stages if getattr(st, "name", None) == stage_name), None)
        if not stage:
            raise HTTPException(status_code=404, detail="Stage not found")
        allowed_fields = {
            "ai",
            "vector_store",
            "graph",
            "graph_summary",
            "frame",
            "match_column",
            "max_rows",
            "group_by",
            "max_rows_per_group",
            "max_items",
            "strategy",
            "max_hops",
            "max_nodes",
            "top_k",
            "method",
            "embedding_model",
            "output_vector_store",
            "image_column",
            "text_column",
        }
        for key, value in changes.items():
            if key in allowed_fields:
                setattr(stage, key, value)
        return {"status": "updated", "stage": _serialize_rag_stage(stage), "pipeline": _serialize_rag_pipeline(pipeline)}

    @app.post("/api/studio/rag/pipelines/{pipeline_id}/preview")
    def api_studio_rag_preview(
        pipeline_id: str, payload: RagPreviewRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = _build_project_engine()
        pipeline = (getattr(engine.program, "rag_pipelines", {}) or {}).get(pipeline_id)
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        query = payload.query
        stage_previews: list[dict[str, Any]] = []
        for st in pipeline.stages:
            stage_previews.append(
                {
                    "stage": st.name,
                    "type": st.type,
                    "summary": f"Configured stage {st.name} ({st.type})",
                    "params": {k: v for k, v in _serialize_rag_stage(st).items() if k not in {"name", "type"}},
                }
            )
        return {"pipeline": _serialize_rag_pipeline(pipeline), "query": query, "stages": stage_previews}

    # ---------- Studio macro inspector endpoints ----------
    @app.get("/api/studio/macros")
    def api_studio_macros(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        invocations = _collect_macro_invocations()
        macros = []
        for macro_id, rec in invocations:
            counts = {k: len(v) for k, v in rec.artifacts.items()}
            macros.append(
                {
                    "id": macro_id,
                    "name": rec.macro_name,
                    "source": rec.source_path,
                    "line": rec.span.line if rec.span else None,
                    "column": rec.span.column if rec.span else None,
                    "artifact_counts": counts,
                }
            )
        return {"macros": macros}

    @app.get("/api/studio/macros/{macro_id}")
    def api_studio_macro_detail(macro_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        invocations = _collect_macro_invocations()
        match = next(((mid, rec) for mid, rec in invocations if mid == macro_id), None)
        if not match:
            raise HTTPException(status_code=404, detail="Macro not found")
        _, rec = match
        return {
            "macro": {
                "id": macro_id,
                "name": rec.macro_name,
                "source": rec.source_path,
                "line": rec.span.line if rec.span else None,
                "column": rec.span.column if rec.span else None,
                "artifacts": rec.artifacts,
            }
        }

    # ---------- Studio traces & errors endpoints ----------
    def _span_kind(span) -> str:
        name = span.name or ""
        attrs = span.attributes or {}
        if name.startswith("flow."):
            return "flow"
        if name.startswith("agent"):
            return "agent"
        if "tool" in name or attrs.get("tool"):
            return "tool"
        if "rag" in name or attrs.get("rag"):
            return "rag"
        return "event"

    def _serialize_span(span) -> Dict[str, Any]:
        duration = None
        if span.end_time and span.start_time:
            duration = span.end_time - span.start_time
        return {
            "trace_id": span.context.trace_id,
            "span_id": span.context.span_id,
            "parent_span_id": span.context.parent_span_id,
            "name": span.name,
            "kind": _span_kind(span),
            "attributes": span.attributes,
            "start_time": span.start_time,
            "end_time": span.end_time,
            "duration": duration,
            "exception": span.exception,
        }

    def _find_span_by_id(span_id: str) -> Any | None:
        for spans in default_tracer.all_traces().values():
            for span in spans:
                if span.context.span_id == span_id:
                    return span
        return None

    @app.get("/api/studio/runs")
    def api_studio_runs(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        traces = default_tracer.all_traces()
        runs = []
        for trace_id, spans in traces.items():
            if not spans:
                continue
            start = min(s.start_time for s in spans if s.start_time) if spans else time.time()
            end = max((s.end_time or time.time()) for s in spans) if spans else start
            label = None
            for s in spans:
                attrs = s.attributes or {}
                if attrs.get("flow"):
                    label = attrs.get("flow")
                    break
                if attrs.get("agent"):
                    label = attrs.get("agent")
            status = "ok"
            if any(s.exception for s in spans):
                status = "error"
            runs.append(
                {
                    "run_id": trace_id,
                    "label": label,
                    "status": status,
                    "start_time": start,
                    "duration": (end - start),
                }
            )
        return {"runs": runs}

    @app.get("/api/studio/runs/{run_id}/trace")
    def api_studio_trace(run_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        spans = sorted(default_tracer.get_trace(run_id), key=lambda s: s.start_time or 0)
        return {"trace": [_serialize_span(s) for s in spans]}

    @app.get("/api/studio/errors/{error_id}")
    def api_studio_error_detail(error_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        span = _find_span_by_id(error_id)
        if not span:
            raise HTTPException(status_code=404, detail="Error not found")
        attrs = span.attributes or {}
        snippet = attrs.get("source") or attrs.get("dsl") or None
        return {
            "id": error_id,
            "message": span.exception or attrs.get("error") or "Unknown error",
            "code": attrs.get("code") or "N3-STUDIO-ERR",
            "dsl_snippet": snippet,
            "ir_context": attrs.get("context"),
            "hints": attrs.get("hints") or [],
        }

    return app
