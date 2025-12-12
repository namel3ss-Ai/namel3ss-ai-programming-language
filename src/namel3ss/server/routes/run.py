"""Execution and tracing API routes."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..deps import Principal, can_run_app, can_run_flow, can_view_traces, get_principal
from ..schemas import RunAppRequest, RunFlowRequest


def build_run_router(
    engine_cls,
    metrics_tracker,
    trigger_manager,
    plugin_registry,
    store_trace: Callable[[Optional[str], Dict[str, Any], str, float, float], Dict[str, Any]],
    store_agent_traces: Callable[[Dict[str, Any], float], None],
    get_last_trace: Callable[[], Optional[Dict[str, Any]]],
    set_last_trace: Callable[[Optional[Dict[str, Any]]], None],
    recent_traces: List[Dict[str, Any]],
    recent_agent_traces: List[Dict[str, Any]],
    resolve_example_path,
    get_examples_root,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/run-app")
    def api_run_app(
        payload: RunAppRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_run_app(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            started_at = time.time()
            engine = engine_cls.from_source(
                payload.source,
                metrics_tracker=metrics_tracker,
                trigger_manager=trigger_manager,
                plugin_registry=plugin_registry,
            )
            result = engine.run_app(
                payload.app_name, include_trace=True, principal_role=principal.role.value
            )
            set_last_trace(result.get("trace"))
            duration = time.time() - started_at
            stored = store_trace(None, get_last_trace(), "completed", started_at, duration)
            store_agent_traces(stored["trace"], duration)
            return {"result": result, "trace": result.get("trace")}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/example-source")
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

    @router.get("/api/last-trace")
    def api_last_trace(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_traces(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        trace = get_last_trace()
        if trace is None:
            raise HTTPException(status_code=404, detail="No trace available")
        return {"trace": trace}

    @router.get("/api/traces")
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

    @router.get("/api/trace/{trace_id}")
    def api_trace(trace_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_traces(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        for rec in recent_traces:
            if rec["id"] == trace_id:
                return rec
        raise HTTPException(status_code=404, detail="Trace not found")

    @router.get("/api/agent-traces")
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

    @router.get("/api/agent-trace/{trace_id}")
    def api_agent_trace(trace_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_traces(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        for rec in recent_agent_traces:
            if rec["id"] == trace_id:
                return rec
        raise HTTPException(status_code=404, detail="Agent trace not found")

    @router.post("/api/run-flow")
    def api_run_flow(
        payload: RunFlowRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            started_at = time.time()
            engine = engine_cls.from_source(
                payload.source,
                metrics_tracker=metrics_tracker,
                trigger_manager=trigger_manager,
                plugin_registry=plugin_registry,
            )
            result = engine.execute_flow(
                payload.flow, principal_role=principal.role.value
            )
            set_last_trace(result.get("trace"))
            duration = time.time() - started_at
            stored = store_trace(payload.flow, get_last_trace(), "completed", started_at, duration)
            store_agent_traces(stored["trace"], duration)
            return {"result": result, "trace": result.get("trace")}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router


__all__ = ["build_run_router"]
