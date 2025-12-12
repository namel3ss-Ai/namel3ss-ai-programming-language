"""Application factory that builds the FastAPI app with all wiring."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from ... import ir
from ...ai.registry import ModelRegistry
from ...config import ProvidersConfig, load_config
from ...diagnostics.runner import collect_diagnostics, collect_lint, iter_ai_files
from ...distributed.file_watcher import FileWatcher
from ...distributed.queue import global_job_queue
from ...distributed.scheduler import JobScheduler
from ...distributed.workers import Worker
from ...examples.manager import resolve_example_path, get_examples_root
from ...flows.models import StreamEvent
from ...flows.triggers import FlowTrigger, TriggerManager
from ...lang.formatter import format_source
from ...memory.inspection import describe_memory_plan, describe_memory_state
from ...metrics.tracker import MetricsTracker
from ...migration.naming import migrate_source_to_naming_standard
from ...obs.tracer import Tracer
from ...optimizer.apply import SuggestionApplier
from ...optimizer.engine import OptimizerEngine
from ...optimizer.overlays import OverlayStore
from ...optimizer.storage import OptimizerStorage
from ...packaging.bundler import Bundler, make_server_bundle, make_worker_bundle
from ...plugins.registry import PluginRegistry
from ...plugins.versioning import CORE_VERSION
from ...runtime.context import ExecutionContext
from ...runtime.engine import Engine
from ...secrets.manager import get_default_secrets_manager
from ...server.schemas import NamingMigrationSummary
from ...studio.ai_calls import describe_ai_call_context
from ...studio.ask import ask_studio
from ...studio.canvas import build_canvas_manifest
from ...studio.daemon import StudioDaemon
from ...studio.flows import list_flows as studio_list_flows, run_flow_once
from ...studio.inspectors import inspect_entity
from ...studio.logs import LogBuffer, log_event
from ...studio.rag import (
    describe_rag_pipeline as studio_describe_rag_pipeline,
    list_rag_pipelines as studio_list_rag_pipelines,
)
from ...studio.warnings import collect_warnings
from .lifecycle import register_lifecycle
from .middleware import setup_middleware
from .policies import (
    compute_scope_keys,
    legacy_session_payload,
    long_term_key,
    long_term_store_name,
    profile_key,
    profile_store_name,
    short_term_store_name,
)
from .project import (
    STUDIO_CONFIG_FILES,
    STUDIO_STATIC_DIR,
    build_project_helpers,
    parse_source_to_ast,
    parse_source_to_ir,
    serialize_stream_event,
)
from .routing import include_routers


@dataclass
class RoutingDeps:
    log_buffer: LogBuffer
    log_event: Callable[..., Any]
    studio_status_payload: Callable[[], Dict[str, Any]]
    project_root: Callable[[], Path]
    project_ui_manifest: Callable[[], Dict[str, Any]]
    get_cached_program: Callable[[], ir.IRProgram | None]
    project_program: Callable[[], ir.IRProgram]
    build_project_engine: Callable[[ir.IRProgram | None], Engine]
    build_engine_from_source: Callable[[str], Engine]
    build_plugin_engine: Callable[[str], Engine]
    parse_source_to_ir: Callable[[str], ir.IRProgram]
    build_canvas_manifest_fn: Callable[[Any], Dict[str, Any]]
    describe_memory_plan_fn: Callable[..., Any]
    describe_memory_state_fn: Callable[..., Any]
    ask_studio_fn: Callable[..., Any]
    describe_ai_call_context_fn: Callable[..., Any]
    inspect_entity_fn: Callable[..., Any]
    studio_list_flows_fn: Callable[..., Any]
    run_flow_once_fn: Callable[..., Any]
    studio_list_rag_pipelines_fn: Callable[..., Any]
    studio_describe_rag_pipeline_fn: Callable[..., Any]
    collect_warnings_fn: Callable[..., Any]
    invalidate_program_cache: Callable[[], None]
    set_cached_program: Callable[[ir.IRProgram | None], None]
    daemon_state: Any
    StudioDaemon_cls: type
    ignored_dirs: set[str]
    metrics_tracker: MetricsTracker
    job_queue: Any
    trigger_manager: TriggerManager
    plugin_registry: PluginRegistry
    naming_migration_summary_cls: Any
    store_trace: Callable[[Optional[str], Dict[str, Any], str, float, float], Dict[str, Any]]
    store_agent_traces: Callable[[Dict[str, Any], float], None]
    get_last_trace: Callable[[], Optional[Dict[str, Any]]]
    set_last_trace: Callable[[Optional[Dict[str, Any]]], None]
    recent_traces: List[Dict[str, Any]]
    recent_agent_traces: List[Dict[str, Any]]
    register_state_subscriber: Callable[[], asyncio.Queue]
    unregister_state_subscriber: Callable[[asyncio.Queue], None]
    broadcast_state_event: Callable[[Dict[str, Any]], Any]
    global_state_stream_callback: Callable[[StreamEvent], Any]
    ExecutionContextCls: type
    optimizer_storage: OptimizerStorage
    overlay_store: OverlayStore
    studio_static_dir: Path | None
    studio_config_files: tuple[str, ...]


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
        job_queue=global_job_queue,
        secrets=get_default_secrets_manager(),
        tracer=Tracer(),
        metrics=metrics_tracker,
        project_root=project_root,
    )
    file_watcher = FileWatcher(trigger_manager, project_root)
    trigger_manager.file_watcher = file_watcher
    optimizer_storage = OptimizerStorage(
        Path(get_default_secrets_manager().get("N3_OPTIMIZER_DB") or "optimizer.db")
    )
    overlay_store = OverlayStore(
        Path(get_default_secrets_manager().get("N3_OPTIMIZER_OVERLAYS") or "optimizer_overlays.json")
    )
    state_subscribers: list[asyncio.Queue] = []

    def _build_engine_from_source(code: str):
        return Engine.from_source(
            code,
            metrics_tracker=metrics_tracker,
            trigger_manager=trigger_manager,
            plugin_registry=plugin_registry,
        )

    def _build_plugin_engine(code: str = "") -> Engine:
        return Engine.from_source(
            code,
            metrics_tracker=metrics_tracker,
            trigger_manager=trigger_manager,
            plugin_registry=plugin_registry,
        )

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

    def _get_last_trace() -> Optional[Dict[str, Any]]:
        return last_trace

    def _set_last_trace(trace: Optional[Dict[str, Any]]) -> None:
        nonlocal last_trace
        last_trace = trace

    async def _global_state_stream_callback(evt: StreamEvent) -> None:
        data = serialize_stream_event(evt)
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

    register_lifecycle(app, file_watcher)
    setup_middleware(app)

    _IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
    (
        _iter_ai_files,
        _studio_status_payload,
        _project_ui_manifest,
        _project_program,
        _build_project_engine,
    ) = build_project_helpers(
        project_root=project_root,
        get_cached_program=_get_cached_program,
        set_cached_program=_set_cached_program,
        log_event_fn=log_event,
        log_buffer=log_buffer,
        ignored_dirs=_IGNORED_DIRS,
        metrics_tracker=metrics_tracker,
        trigger_manager=trigger_manager,
        plugin_registry=plugin_registry,
        daemon_state=daemon_state,
    )

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

    routing_deps = RoutingDeps(
        log_buffer=log_buffer,
        log_event=log_event,
        studio_status_payload=_studio_status_payload,
        project_root=_project_root,
        project_ui_manifest=_project_ui_manifest,
        get_cached_program=_get_cached_program,
        project_program=_project_program,
        build_project_engine=_build_project_engine,
        build_engine_from_source=_build_engine_from_source,
        build_plugin_engine=_build_plugin_engine,
        parse_source_to_ir=parse_source_to_ir,
        build_canvas_manifest_fn=None,  # placeholder; set below
        describe_memory_plan_fn=describe_memory_plan,
        describe_memory_state_fn=describe_memory_state,
        ask_studio_fn=ask_studio,
        describe_ai_call_context_fn=describe_ai_call_context,
        inspect_entity_fn=inspect_entity,
        studio_list_flows_fn=studio_list_flows,
        run_flow_once_fn=run_flow_once,
        studio_list_rag_pipelines_fn=studio_list_rag_pipelines,
        studio_describe_rag_pipeline_fn=studio_describe_rag_pipeline,
        collect_warnings_fn=collect_warnings,
        invalidate_program_cache=_invalidate_program_cache,
        set_cached_program=_set_cached_program,
        daemon_state=daemon_state,
        StudioDaemon_cls=StudioDaemon,
        ignored_dirs=_IGNORED_DIRS,
        metrics_tracker=metrics_tracker,
        job_queue=global_job_queue,
        trigger_manager=trigger_manager,
        plugin_registry=plugin_registry,
        naming_migration_summary_cls=NamingMigrationSummary,
        store_trace=_store_trace,
        store_agent_traces=_store_agent_traces,
        get_last_trace=lambda: last_trace,
        set_last_trace=_set_last_trace,
        recent_traces=recent_traces,
        recent_agent_traces=recent_agent_traces,
        register_state_subscriber=_register_state_subscriber,
        unregister_state_subscriber=_unregister_state_subscriber,
        broadcast_state_event=_broadcast_state_event,
        global_state_stream_callback=_global_state_stream_callback,
        ExecutionContextCls=ExecutionContext,
        optimizer_storage=optimizer_storage,
        overlay_store=overlay_store,
        studio_static_dir=STUDIO_STATIC_DIR,
        studio_config_files=STUDIO_CONFIG_FILES,
    )

    routing_deps.build_canvas_manifest_fn = build_canvas_manifest
    routing_deps.naming_migration_summary_cls = NamingMigrationSummary

    include_routers(app, routing_deps)

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

    return app


__all__ = ["create_app", "RoutingDeps"]
