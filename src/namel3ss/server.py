"""
FastAPI surface for Namel3ss V3.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional, List
from pathlib import Path
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ir, lexer, parser
from .errors import ParseError
from .lang.formatter import format_source
from .flows.triggers import FlowTrigger, TriggerManager
from .runtime.engine import Engine
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
from .distributed.scheduler import JobScheduler
from .distributed.workers import Worker
from .metrics.tracker import MetricsTracker
from .studio.engine import StudioEngine
from .diagnostics.runner import collect_diagnostics, iter_ai_files
from .packaging.bundler import Bundler, make_server_bundle, make_worker_bundle
from .secrets.manager import SecretsManager
from .plugins.registry import PluginRegistry
from .plugins.versioning import CORE_VERSION
from .optimizer.storage import OptimizerStorage
from .optimizer.overlays import OverlayStore
from .optimizer.engine import OptimizerEngine
from .optimizer.apply import SuggestionApplier

BASE_DIR = Path(__file__).resolve().parents[2]
STUDIO_STATIC_DIR = BASE_DIR / "studio" / "static"


class ParseRequest(BaseModel):
    source: str


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
        job_queue=global_job_queue, secrets=SecretsManager(), tracer=Tracer(), metrics=metrics_tracker
    )
    optimizer_storage = OptimizerStorage(Path(SecretsManager().get("N3_OPTIMIZER_DB") or "optimizer.db"))
    overlay_store = OverlayStore(Path(SecretsManager().get("N3_OPTIMIZER_OVERLAYS") or "optimizer_overlays.json"))

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
            success = summary["errors"] == 0
            return {
                "success": success,
                "diagnostics": [] if payload.summary_only else [d.to_dict() for d in diags],
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
        # Build a minimal runtime for counting
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
