from __future__ import annotations

from typing import Any, Callable, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from ....runtime.engine import Engine
from ....studio.engine import StudioEngine
from ....obs.tracer import Tracer
from ...deps import Principal, Role, can_run_flow, can_view_pages, get_principal
from ...schemas import FlowsRequest
from ...services.studio_service import (
    ask_studio_service,
    collect_studio_warnings,
    describe_ai_call,
    get_canvas_manifest,
    inspect_entity_payload,
    list_studio_flows,
    log_note,
    reparse_studio,
    run_studio_flow,
)


def register_base_routes(
    router: APIRouter,
    *,
    log_event,
    log_buffer,
    studio_status_payload: Callable[[], Dict[str, Any]],
    get_program: Callable[..., Any],
    build_project_engine: Callable[[Any], Any],
    parse_source_to_ir: Callable[[str], Any],
    build_canvas_manifest_fn,
    describe_memory_plan_fn,
    describe_memory_state_fn,
    ask_studio_fn,
    describe_ai_call_context_fn,
    inspect_entity_fn,
    studio_list_flows_fn,
    run_flow_once_fn,
    collect_warnings_fn,
    invalidate_program_cache: Callable[[], None],
    set_cached_program: Callable[[Any], None],
    daemon_state,
    StudioDaemon_cls,
    job_queue,
    trigger_manager,
    plugin_registry,
    metrics_tracker,
) -> None:
    """Register the core Studio routes."""

    @router.get("/api/studio/canvas")
    def api_studio_canvas() -> Dict[str, Any]:
        return get_canvas_manifest(
            get_program=get_program,
            build_canvas_manifest=build_canvas_manifest_fn,
            log_event=log_event,
            log_buffer=log_buffer,
        )

    @router.post("/api/studio/log-note")
    def api_studio_log_note(payload: Dict[str, Any]) -> Dict[str, Any]:
        return log_note(log_event, log_buffer, payload)

    @router.get("/api/studio/inspect")
    def api_studio_inspect(kind: str, name: str) -> Dict[str, Any]:
        return inspect_entity_payload(
            get_program=get_program,
            inspect_entity_fn=inspect_entity_fn,
            log_event=log_event,
            log_buffer=log_buffer,
            kind=kind,
            name=name,
        )

    @router.post("/api/studio/ask")
    def api_studio_ask(payload: Dict[str, Any]) -> Dict[str, Any]:
        question = (payload.get("question") or "").strip()
        mode = (payload.get("mode") or "explain").strip() or "explain"
        context_payload = payload.get("context") or {}
        status_payload = studio_status_payload()
        return ask_studio_service(
            question=question,
            mode=mode,
            context_payload=context_payload,
            status_payload=status_payload,
            get_program=get_program,
            build_project_engine=build_project_engine,
            describe_memory_plan_fn=describe_memory_plan_fn,
            describe_memory_state_fn=describe_memory_state_fn,
            ask_studio_fn=ask_studio_fn,
            describe_ai_call_context_fn=describe_ai_call_context_fn,
            log_event=log_event,
            log_buffer=log_buffer,
        )

    @router.post("/api/flows")
    def api_flows(payload: FlowsRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role) and not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            program = parse_source_to_ir(payload.code)
            flows = [
                {"name": flow.name, "description": flow.description, "steps": len(flow.steps)}
                for flow in program.flows.values()
            ]
            return {"flows": flows}
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/studio/flows")
    def api_studio_flows() -> Dict[str, Any]:
        return list_studio_flows(
            get_program=get_program,
            studio_list_flows_fn=studio_list_flows_fn,
            daemon_state=daemon_state,
            log_event=log_event,
            log_buffer=log_buffer,
        )

    @router.post("/api/studio/run-flow")
    def api_studio_run_flow(payload: Dict[str, Any]) -> Dict[str, Any]:
        flow_name = (payload.get("flow") or "").strip()
        state = payload.get("input") or payload.get("state") or {}
        metadata = payload.get("metadata") or {}
        return run_studio_flow(
            get_program=get_program,
            run_flow_once_fn=run_flow_once_fn,
            log_event=log_event,
            log_buffer=log_buffer,
            daemon_state=daemon_state,
            flow_name=flow_name,
            state=state,
            metadata=metadata,
        )

    @router.get("/api/studio/ai-call")
    def api_studio_ai_call(ai_id: str = Query(..., alias="ai"), session_id: str = Query(..., alias="session")) -> Dict[str, Any]:
        return describe_ai_call(
            get_program=get_program,
            build_project_engine=build_project_engine,
            describe_ai_call_context_fn=describe_ai_call_context_fn,
            log_event=log_event,
            log_buffer=log_buffer,
            ai_id=ai_id,
            session_id=session_id,
        )

    @router.get("/api/studio/warnings")
    def api_studio_warnings() -> Dict[str, Any]:
        return collect_studio_warnings(
            get_program=get_program,
            collect_warnings_fn=collect_warnings_fn,
            log_event=log_event,
            log_buffer=log_buffer,
            daemon_state=daemon_state,
        )

    @router.post("/api/studio/reparse")
    def api_studio_reparse() -> Dict[str, Any]:
        return reparse_studio(
            daemon_state=daemon_state,
            StudioDaemon_cls=StudioDaemon_cls,
            set_cached_program=set_cached_program,
            invalidate_program_cache=invalidate_program_cache,
            project_program=project_program,
            log_event=log_event,
            log_buffer=log_buffer,
        )

    @router.get("/api/studio-summary")
    def api_studio_summary(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = build_project_engine()
        except HTTPException:
            engine = Engine.from_source(
                "",
                metrics_tracker=metrics_tracker,
                trigger_manager=trigger_manager,
                plugin_registry=plugin_registry,
            )
        except Exception:
            engine = Engine.from_source(
                "",
                metrics_tracker=metrics_tracker,
                trigger_manager=trigger_manager,
                plugin_registry=plugin_registry,
            )
        studio = StudioEngine(
            job_queue=job_queue,
            tracer=Tracer(),
            metrics_tracker=metrics_tracker,
            memory_engine=engine.memory_engine,
            rag_engine=engine.rag_engine,
            ir_program=engine.program,
            plugin_registry=engine.plugin_registry,
        )
        summary = studio.build_summary()
        return {"summary": summary.__dict__}


__all__ = ["register_base_routes"]
