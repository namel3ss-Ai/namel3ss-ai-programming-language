from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ...deps import Principal, Role, get_principal
from ....observability.tracing import default_tracer


def register_trace_routes(router: APIRouter) -> None:
    """Register trace and error inspection routes."""

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

    @router.get("/api/studio/runs")
    def api_studio_runs(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        traces = default_tracer.all_traces()
        runs = []
        for trace_id, spans in traces.items():
            if not spans:
                continue
            start = min(s.start_time for s in spans if s.start_time) if spans else 0
            end = max((s.end_time or 0) for s in spans) if spans else start
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

    @router.get("/api/studio/runs/{run_id}/trace")
    def api_studio_trace(run_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        spans = sorted(default_tracer.get_trace(run_id), key=lambda s: s.start_time or 0)
        return {"trace": [_serialize_span(s) for s in spans]}

    @router.get("/api/studio/errors/{error_id}")
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


__all__ = ["register_trace_routes"]
