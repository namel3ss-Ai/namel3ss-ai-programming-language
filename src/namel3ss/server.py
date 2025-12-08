"""
FastAPI surface for Namel3ss V3.
"""

from __future__ import annotations

import os
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ir, lexer, parser
from .ai.registry import ModelRegistry
from .config import N3Config, ProvidersConfig, load_config
from .errors import ParseError
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
from .diagnostics.runner import collect_diagnostics, collect_lint, iter_ai_files
from . import linting
from .packaging.bundler import Bundler, make_server_bundle, make_worker_bundle
from .secrets.manager import SecretsManager
from .plugins.registry import PluginRegistry
from .plugins.versioning import CORE_VERSION
from .optimizer.storage import OptimizerStorage
from .optimizer.overlays import OverlayStore
from .optimizer.engine import OptimizerEngine
from .optimizer.apply import SuggestionApplier
from .examples.manager import resolve_example_path, get_examples_root
from .ui.manifest import build_ui_manifest
from .flows.models import StreamEvent

BASE_DIR = Path(__file__).resolve().parents[2]
STUDIO_STATIC_DIR = BASE_DIR / "studio" / "static"


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


def _parse_source_to_ast(source: str) -> Dict[str, Any]:
    tokens = lexer.Lexer(source).tokenize()
    module = parser.Parser(tokens).parse_module()
    return asdict(module)


def _parse_source_to_ir(source: str) -> ir.IRProgram:
    tokens = lexer.Lexer(source).tokenize()
    module = parser.Parser(tokens).parse_module()
    return ir.ast_to_ir(module)


def create_app() -> FastAPI:
    """Create the FastAPI app."""

    project_root = Path.cwd().resolve()
    app = FastAPI(title="Namel3ss V3", version="0.1.0")
    if STUDIO_STATIC_DIR.exists():
        app.mount(
            "/studio-static",
            StaticFiles(directory=str(STUDIO_STATIC_DIR)),
            name="studio-static",
        )
    last_trace: Optional[Dict[str, Any]] = None
    recent_traces: List[Dict[str, Any]] = []
    recent_agent_traces: List[Dict[str, Any]] = []
    metrics_tracker = MetricsTracker()
    plugin_registry = PluginRegistry(Path(SecretsManager().get("N3_PLUGINS_DIR") or "plugins"), core_version=CORE_VERSION, tracer=Tracer())
    trigger_manager = TriggerManager(
        job_queue=global_job_queue, secrets=SecretsManager(), tracer=Tracer(), metrics=metrics_tracker, project_root=project_root
    )
    file_watcher = FileWatcher(trigger_manager, project_root)
    trigger_manager.file_watcher = file_watcher
    optimizer_storage = OptimizerStorage(Path(SecretsManager().get("N3_OPTIMIZER_DB") or "optimizer.db"))
    overlay_store = OverlayStore(Path(SecretsManager().get("N3_OPTIMIZER_OVERLAYS") or "optimizer_overlays.json"))
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
        base = _project_root()
        sources: list[str] = []
        for path in _iter_ai_files(base):
            sources.append(path.read_text(encoding="utf-8"))
        if not sources:
            raise HTTPException(status_code=400, detail="No .ai files found")
        combined = "\n\n".join(sources)
        return Engine._load_program(combined, filename=str(base / "project.ai"))

    def _build_project_engine(program: ir.IRProgram | None = None) -> Engine:
        prog = program or _project_program()
        return Engine(
            prog,
            metrics_tracker=metrics_tracker,
            trigger_manager=trigger_manager,
            plugin_registry=plugin_registry,
        )

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

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

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
        index_path = STUDIO_STATIC_DIR / "index.html"
        if not index_path.exists():
            return HTMLResponse(
                "<html><body><h1>Studio assets not found.</h1></body></html>",
                status_code=500,
            )
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
        memory_stores = engine.memory_stores
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
        short_history: List[Dict[str, Any]] = []
        if short_backend:
            short_history = short_backend.get_full_history(short_scope["ai_key"], short_scope["session_key"])
            short_history = filter_turns_by_retention(
                short_history,
                getattr(short_cfg, "retention_days", None) if short_cfg else None,
            )
        short_window = (
            getattr(short_cfg, "window", None)
            or getattr(mem_cfg, "window", None)
            or DEFAULT_SHORT_TERM_WINDOW
        )
        long_cfg = getattr(mem_cfg, "long_term", None)
        long_scope = (
            _compute_scope_keys("long_term", getattr(long_cfg, "scope", None), _long_term_key(ai_id), session_id, session_user_id)
            if long_cfg
            else None
        )
        long_store_name = _long_term_store_name(mem_cfg)
        long_items: List[Dict[str, Any]] = []
        if (
            long_scope
            and long_store_name
            and long_store_name in memory_stores
        ):
            long_backend = memory_stores[long_store_name]
            long_items = long_backend.list_items(long_scope["ai_key"], long_scope["session_key"])
            long_items = filter_items_by_retention(
                long_items,
                getattr(long_cfg, "retention_days", None),
            )
        profile_cfg = getattr(mem_cfg, "profile", None)
        profile_scope = (
            _compute_scope_keys("profile", getattr(profile_cfg, "scope", None), _profile_key(ai_id), session_id, session_user_id)
            if profile_cfg
            else None
        )
        profile_store_name = _profile_store_name(mem_cfg)
        profile_facts: List[str] = []
        if (
            profile_scope
            and profile_store_name
            and profile_store_name in memory_stores
        ):
            profile_backend = memory_stores[profile_store_name]
            profile_history = profile_backend.get_full_history(profile_scope["ai_key"], profile_scope["session_key"])
            profile_history = filter_turns_by_retention(
                profile_history,
                getattr(profile_cfg, "retention_days", None),
            )
            profile_facts = [
                turn.get("content", "")
                for turn in profile_history
                if (turn.get("role") or "").lower() == "system"
            ]
        policies = {
            "short_term": _build_policy_info("short_term", short_cfg, short_scope, session_user_id),
            "long_term": _build_policy_info("long_term", long_cfg, long_scope, session_user_id),
            "profile": _build_policy_info("profile", profile_cfg, profile_scope, session_user_id),
        }
        snapshot = get_last_recall_snapshot(ai_id, session_id)
        return {
            "ai": ai_id,
            "session": session_id,
            "user_id": session_user_id,
            "short_term": {
                "window": short_window,
                "turns": short_history,
            },
            "long_term": {"store": long_store_name, "items": long_items} if long_store_name else None,
            "profile": {"store": profile_store_name, "facts": profile_facts} if profile_store_name else None,
            "policies": policies,
            "last_recall_snapshot": snapshot,
        }

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
            secrets=SecretsManager(),
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

    return app
