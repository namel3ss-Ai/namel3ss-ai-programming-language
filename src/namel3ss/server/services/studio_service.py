"""Service helpers for Studio-related routes."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import HTTPException

from ..errors import Namel3ssError


def get_canvas_manifest(get_program, build_canvas_manifest, log_event, log_buffer):
    try:
        program = get_program()
        if program is None:
            program = get_program(force_project=True)
        return build_canvas_manifest(program)
    except Exception as exc:  # pragma: no cover - defensive
        log_event(log_buffer, "canvas_error", level="error", message=str(exc))
        return {"nodes": [], "edges": [], "status": "error", "error": str(exc)}


def log_note(log_event, log_buffer, payload: Dict[str, Any]) -> Dict[str, Any]:
    event = payload.get("event") or "note"
    level = payload.get("level") or "info"
    details = payload.get("details") or {}
    log_event(log_buffer, event, level=level, **details)
    return {"ok": True}


def inspect_entity_payload(get_program, inspect_entity_fn, log_event, log_buffer, kind: str, name: str) -> Dict[str, Any]:
    try:
        program = get_program() or get_program(force_project=True)
        entity = inspect_entity_fn(program, kind, name)
        log_event(log_buffer, "inspector_opened", level="info", kind=kind, name=name)
        return entity
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        log_event(log_buffer, "inspector_error", level="error", kind=kind, name=name, message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


def ask_studio_service(
    question: str,
    mode: str,
    context_payload: Dict[str, Any],
    status_payload: Dict[str, Any],
    get_program,
    build_project_engine,
    describe_memory_plan_fn,
    describe_memory_state_fn,
    ask_studio_fn,
    describe_ai_call_context_fn,
    log_event,
    log_buffer,
) -> Dict[str, Any]:
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    entity_payload = None
    try:
        kind = context_payload.get("kind")
        name = context_payload.get("name")
        if kind and name:
            program = get_program() or get_program(force_project=True)
            entity_payload = describe_ai_call_context_fn(program, kind, name)
    except Exception:
        entity_payload = None
    memory_payload = None
    memory_state_payload = None
    ai_id = context_payload.get("ai_id")
    session_id = context_payload.get("session_id")
    if ai_id:
        try:
            program = get_program(force_project=True)
            ai_calls = getattr(program, "ai_calls", {}) or {}
            if ai_id in ai_calls:
                memory_payload = describe_memory_plan_fn(ai_calls[ai_id])
                if session_id:
                    engine = build_project_engine(program)
                    memory_state_payload = describe_memory_state_fn(engine, ai_calls[ai_id], session_id=session_id, limit=25)
        except Exception:
            memory_payload = memory_payload or {"ai": ai_id, "error": "Unable to load memory."}
    try:
        result = ask_studio_fn(
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


def list_studio_flows(get_program, studio_list_flows_fn, daemon_state, log_event, log_buffer) -> Dict[str, Any]:
    try:
        program = get_program()
        if program is None and daemon_state is not None and getattr(daemon_state, "last_error_detail", None):
            raise HTTPException(status_code=503, detail=getattr(daemon_state, "last_error_detail"))
        program = program or get_program(force_project=True)
        return {"flows": studio_list_flows_fn(program)}
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        log_event(log_buffer, "flows_list_error", level="error", message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


def run_studio_flow(get_program, run_flow_once_fn, log_event, log_buffer, daemon_state, flow_name: str, state, metadata) -> Dict[str, Any]:
    if not flow_name:
        raise HTTPException(status_code=400, detail="Missing flow name")
    try:
        program = get_program()
        if program is None and daemon_state is not None and getattr(daemon_state, "last_error_detail", None):
            raise HTTPException(status_code=503, detail=getattr(daemon_state, "last_error_detail"))
        program = program or get_program(force_project=True)
        log_event(log_buffer, "flow_run_started", level="info", flow=flow_name)
        result = run_flow_once_fn(program, flow_name, state=state, metadata=metadata)
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


def describe_ai_call(get_program, build_project_engine, describe_ai_call_context_fn, log_event, log_buffer, ai_id: str, session_id: str) -> Dict[str, Any]:
    ai_id = (ai_id or "").strip()
    session_id = (session_id or "").strip()
    if not ai_id or not session_id:
        raise HTTPException(status_code=400, detail="ai and session are required")
    try:
        program = get_program() or get_program(force_project=True)
        engine = build_project_engine(program)
        payload = describe_ai_call_context_fn(program, ai_id, session_id, engine)
        log_event(log_buffer, "ai_call_visualized", level="info", ai=ai_id, session=session_id)
        return payload
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        log_event(log_buffer, "ai_call_visualizer_error", level="error", ai=ai_id, session=session_id, message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


def list_rag_pipelines(get_program, studio_list_rag_pipelines_fn, log_event, log_buffer) -> Dict[str, Any]:
    try:
        program = get_program() or get_program(force_project=True)
        pipelines = studio_list_rag_pipelines_fn(program)
        return {"pipelines": pipelines}
    except KeyError:
        raise HTTPException(status_code=404, detail="No rag pipelines found")
    except Exception as exc:  # pragma: no cover - defensive
        log_event(log_buffer, "rag_list_error", level="error", message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


def describe_rag_pipeline(get_program, studio_describe_rag_pipeline_fn, log_event, log_buffer, name: str) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Missing pipeline name")
    try:
        program = get_program() or get_program(force_project=True)
        manifest = studio_describe_rag_pipeline_fn(program, name)
        log_event(log_buffer, "rag_pipeline_viewed", level="info", pipeline=name)
        return manifest
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        log_event(log_buffer, "rag_pipeline_error", level="error", pipeline=name, message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


def collect_studio_warnings(get_program, collect_warnings_fn, log_event, log_buffer, daemon_state) -> Dict[str, Any]:
    try:
        program = get_program()
        if program is None and daemon_state is not None and getattr(daemon_state, "last_error_detail", None):
            return {"warnings": []}
        program = program or get_program(force_project=True)
        warnings = collect_warnings_fn(program)
        log_event(log_buffer, "warnings_collected", level="info", count=len(warnings))
        return {"warnings": warnings}
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        log_event(log_buffer, "warnings_error", level="error", message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))


def reparse_studio(
    daemon_state,
    StudioDaemon_cls,
    set_cached_program,
    invalidate_program_cache,
    project_program,
    log_event,
    log_buffer,
) -> Dict[str, Any]:
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    errors: list[dict[str, Any]] = []
    success = False
    try:
        if isinstance(daemon_state, StudioDaemon_cls):
            program = daemon_state.ensure_program(raise_on_error=False)
            set_cached_program(program)
            if daemon_state.last_error_detail:
                detail = daemon_state.last_error_detail or {}
                if isinstance(detail, dict):
                    errors.append(detail)
            success = program is not None and not errors
        else:
            invalidate_program_cache()
            try:
                program = project_program()
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


__all__ = [
    "get_canvas_manifest",
    "log_note",
    "inspect_entity_payload",
    "ask_studio_service",
    "list_studio_flows",
    "run_studio_flow",
    "describe_ai_call",
    "list_rag_pipelines",
    "describe_rag_pipeline",
    "collect_studio_warnings",
    "reparse_studio",
]
