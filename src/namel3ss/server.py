"""
FastAPI surface for Namel3ss V3.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from . import ir, lexer, parser
from .runtime.engine import Engine
from .ui.renderer import UIRenderer
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
from .diagnostics.pipeline import run_diagnostics
from .diagnostics.models import has_effective_errors
from .packaging.bundler import Bundler, make_server_bundle, make_worker_bundle


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
    code: str


class BundleRequest(BaseModel):
    code: str
    target: str | None = "server"


class RAGQueryRequest(BaseModel):
    code: str
    query: str
    indexes: Optional[list[str]] = None


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
    last_trace: Optional[Dict[str, Any]] = None
    metrics_tracker = MetricsTracker()

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/parse")
    def api_parse(payload: ParseRequest) -> Dict[str, Any]:
        try:
            return {"ast": _parse_source_to_ast(payload.source)}
        except Exception as exc:  # pragma: no cover - FastAPI handles tracebacks
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/run-app")
    def api_run_app(
        payload: RunAppRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_run_app(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = Engine.from_source(payload.source, metrics_tracker=metrics_tracker)
            result = engine.run_app(
                payload.app_name, include_trace=True, principal_role=principal.role.value
            )
            nonlocal last_trace
            last_trace = result.get("trace")
            return {"result": result, "trace": result.get("trace")}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/studio")
    def studio() -> Dict[str, str]:
        return {"message": "Studio coming soon"}

    @app.get("/api/last-trace")
    def api_last_trace(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_traces(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        if last_trace is None:
            raise HTTPException(status_code=404, detail="No trace available")
        return {"trace": last_trace}

    @app.post("/api/run-flow")
    def api_run_flow(
        payload: RunFlowRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = Engine.from_source(payload.source, metrics_tracker=metrics_tracker)
            result = engine.execute_flow(
                payload.flow, principal_role=principal.role.value
            )
            nonlocal last_trace
            last_trace = result.get("trace")
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
            engine = Engine.from_source(payload.code)
            if payload.page not in engine.program.pages:
                raise HTTPException(status_code=404, detail="Page not found")
            ui_page = engine.ui_renderer.from_ir_page(engine.program.pages[payload.page])
            return {"ui": ui_page.__dict__}
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/diagnostics")
    def api_diagnostics(
        payload: DiagnosticsRequest,
        strict: bool = False,
        format: str = "json",
        principal: Principal = Depends(get_principal),
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            ir_program = _parse_source_to_ir(payload.code)
            diagnostics = run_diagnostics(ir_program, available_plugins=set())
            summary = {
                "error_count": sum(1 for d in diagnostics if (d.severity or d.level) == "error"),
                "warning_count": sum(1 for d in diagnostics if (d.severity or d.level) == "warning"),
                "strict": bool(strict),
                "has_errors": has_effective_errors(diagnostics, strict),
            }
            payload_out = {
                "summary": summary,
                "diagnostics": [d.to_dict() for d in diagnostics],
            }
            if format == "text":
                text_lines = []
                for d in diagnostics:
                    loc = f" {d.location}" if d.location else ""
                    hint = f" (hint: {d.hint})" if d.hint else ""
                    text_lines.append(f"[{d.severity}][{d.code}]{loc} - {d.message}{hint}")
                payload_out["text"] = "\n".join(text_lines)
            return payload_out
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
        engine = Engine.from_source("")
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
        runtime_factory=lambda code: Engine.from_source(code or "", metrics_tracker=metrics_tracker),
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
            engine = Engine.from_source(payload.code, metrics_tracker=metrics_tracker)
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

    @app.get("/api/jobs")
    def api_jobs(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"jobs": [job.__dict__ for job in global_job_queue.list()]}

    @app.get("/api/studio-summary")
    def api_studio_summary(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        # Build a minimal runtime for counting
        engine = Engine.from_source("", metrics_tracker=metrics_tracker)
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
