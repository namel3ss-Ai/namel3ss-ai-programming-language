"""
Helpers to list and execute flows for Studio endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..errors import Namel3ssError
from ..runtime.engine import Engine


def list_flows(program) -> List[dict]:
    flows = getattr(program, "flows", {}) or {}
    descriptors: list[dict] = []
    for name, flow in flows.items():
        descriptors.append(
            {
                "name": name,
                "description": getattr(flow, "description", None),
                "steps": len(getattr(flow, "steps", []) or []),
            }
        )
    return sorted(descriptors, key=lambda entry: entry["name"])


def run_flow_once(program, flow_name: str, state: Dict[str, Any] | None = None, metadata: Dict[str, Any] | None = None) -> dict:
    flows = getattr(program, "flows", {}) or {}
    flow = flows.get(flow_name)
    if not flow:
        raise KeyError(f"flow '{flow_name}' not found")
    engine = Engine(program)
    payload = {"state": state or {}}
    if metadata:
        payload["metadata"] = metadata
    try:
        result = engine.execute_flow(flow_name, payload=payload, principal_role="developer")
    except Namel3ssError as exc:
        return {
            "flow": flow_name,
            "success": False,
            "errors": [str(exc)],
            "steps": [],
            "final_state": state or {},
        }
    steps_payload: list[dict] = []
    for idx, step in enumerate(result.get("steps", []) or []):
        output = step.get("output")
        preview = None
        if output is not None:
            preview = str(output)
            if len(preview) > 200:
                preview = preview[:200]
        ai_id = step.get("target") if step.get("kind") == "ai" else None
        steps_payload.append(
            {
                "index": idx,
                "name": step.get("step_name") or step.get("name"),
                "kind": step.get("kind"),
                "target": step.get("target"),
                "ai_id": ai_id,
                "success": step.get("success"),
                "error": step.get("error_message") or step.get("error"),
                "output_preview": preview,
                "duration_seconds": step.get("duration_seconds"),
                "cost": step.get("cost"),
                "session_id": step.get("session_id"),
                "memory_kinds_used": step.get("memory_kinds_used") or step.get("memory_kinds"),
                "rag_pipeline": step.get("rag_pipeline"),
                "vector_store": step.get("vector_store"),
                "tool_method": step.get("tool_method"),
                "tool_url": step.get("tool_url"),
                "logs_ref": step.get("logs_ref"),
            }
        )
    errors = [err.get("error") or err.get("message") for err in result.get("errors", []) or [] if err]
    state_payload = result.get("state") or {}
    final_state = state_payload.get("data") if isinstance(state_payload, dict) else {}
    session_id = None
    try:
        session_id = (result.get("state") or {}).get("context", {}).get("request_id")
    except Exception:
        session_id = None
    return {
        "flow": flow_name,
        "success": not errors,
        "errors": [e for e in errors if e],
        "steps": steps_payload,
        "final_state": final_state or {},
        "session_id": session_id,
    }
