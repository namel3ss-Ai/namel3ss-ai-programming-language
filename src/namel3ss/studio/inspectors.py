"""
Inspector utilities for Studio: build read-only descriptions of IR entities.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .. import ir


def _base_payload(kind: str, name: str) -> dict:
    return {"kind": kind, "id": f"{kind}:{name}", "name": name}


def inspect_app(program: ir.IRProgram, name: str) -> dict:
    app = (program.apps or {}).get(name)
    if not app:
        raise KeyError(f"app '{name}' not found")
    payload = _base_payload("app", name)
    payload.update(
        {
            "entry_page": getattr(app, "entry_page", None),
            "description": getattr(app, "description", None),
        }
    )
    return payload


def inspect_page(program: ir.IRProgram, name: str) -> dict:
    page = (program.pages or {}).get(name)
    if not page:
        raise KeyError(f"page '{name}' not found")
    payload = _base_payload("page", name)
    app_name = None
    for app in (program.apps or {}).values():
        if getattr(app, "entry_page", None) == name:
            app_name = app.name
            break
    payload.update(
        {
            "route": getattr(page, "route", None),
            "app": app_name,
            "ai_calls": list(getattr(page, "ai_calls", []) or []),
            "agents": list(getattr(page, "agents", []) or []),
            "memories": list(getattr(page, "memories", []) or []),
            "sections": len(getattr(page, "sections", []) or []),
            "layout_blocks": len(getattr(page, "layout", []) or []),
        }
    )
    return payload


def inspect_flow(program: ir.IRProgram, name: str) -> dict:
    flow = (program.flows or {}).get(name)
    if not flow:
        raise KeyError(f"flow '{name}' not found")
    payload = _base_payload("flow", name)
    steps = getattr(flow, "steps", []) or []
    ai_refs: List[str] = []
    agent_refs: List[str] = []
    tool_refs: List[str] = []
    flow_refs: List[str] = []
    for step in steps:
        kind = getattr(step, "kind", None)
        target = getattr(step, "target", None)
        if not target:
            continue
        if kind == "ai":
            ai_refs.append(target)
        elif kind == "agent":
            agent_refs.append(target)
        elif kind == "tool":
            tool_refs.append(target)
        elif kind == "goto_flow":
            flow_refs.append(target)
    payload.update(
        {
            "steps": len(steps),
            "ai_calls": sorted(set(ai_refs)),
            "agents": sorted(set(agent_refs)),
            "tools": sorted(set(tool_refs)),
            "flows": sorted(set(flow_refs)),
            "description": getattr(flow, "description", None),
        }
    )
    return payload


def inspect_ai(program: ir.IRProgram, name: str) -> dict:
    ai_call = (program.ai_calls or {}).get(name)
    if not ai_call:
        raise KeyError(f"ai '{name}' not found")
    payload = _base_payload("ai", name)
    tools = [tb.internal_name or tb.exposed_name for tb in getattr(ai_call, "tools", []) or [] if tb]
    payload.update(
        {
            "model": getattr(ai_call, "model_name", None),
            "memory": getattr(ai_call, "memory_name", None),
            "has_memory": bool(getattr(ai_call, "memory", None) or getattr(ai_call, "memory_name", None)),
            "tools": [t for t in tools if t],
            "description": getattr(ai_call, "description", None),
            "system_prompt": getattr(ai_call, "system_prompt", None),
        }
    )
    return payload


def inspect_agent(program: ir.IRProgram, name: str) -> dict:
    agent = (program.agents or {}).get(name)
    if not agent:
        raise KeyError(f"agent '{name}' not found")
    payload = _base_payload("agent", name)
    payload.update(
        {
            "goal": getattr(agent, "goal", None),
            "personality": getattr(agent, "personality", None),
            "memory": getattr(agent, "memory_name", None),
            "can_delegate_to": getattr(agent, "can_delegate_to", None) or [],
        }
    )
    return payload


def inspect_tool(program: ir.IRProgram, name: str) -> dict:
    tool = (program.tools or {}).get(name)
    if not tool:
        raise KeyError(f"tool '{name}' not found")
    payload = _base_payload("tool", name)
    payload.update(
        {
            "tool_kind": getattr(tool, "kind", None),
            "method": getattr(tool, "method", None),
            "url": getattr(tool, "url_template", None),
            "function": getattr(tool, "function", None),
            "input_fields": getattr(tool, "input_fields", None) or [],
            "auth": getattr(getattr(tool, "auth", None), "kind", None) if getattr(tool, "auth", None) else None,
        }
    )
    return payload


def inspect_memory(program: ir.IRProgram, name: str) -> dict:
    memory = (program.memories or {}).get(name)
    if not memory:
        raise KeyError(f"memory '{name}' not found")
    payload = _base_payload("memory", name)
    payload.update(
        {
            "memory_type": getattr(memory, "memory_type", None),
            "retention": getattr(memory, "retention", None),
        }
    )
    return payload


def inspect_rag_pipeline(program: ir.IRProgram, name: str) -> dict:
    pipeline = (program.rag_pipelines or {}).get(name)
    if not pipeline:
        raise KeyError(f"rag pipeline '{name}' not found")
    payload = _base_payload("rag", name)
    payload.update(
        {
            "default_vector_store": getattr(pipeline, "default_vector_store", None),
            "stages": [getattr(stage, "kind", None) for stage in getattr(pipeline, "stages", []) or []],
        }
    )
    return payload


def inspect_evaluation(program: ir.IRProgram, kind: str, name: str) -> dict:
    mapping = {
        "rag_eval": getattr(program, "rag_evaluations", {}) or {},
        "tool_eval": getattr(program, "tool_evaluations", {}) or {},
        "agent_eval": getattr(program, "agent_evaluations", {}) or {},
    }
    store = mapping.get(kind) or {}
    target = store.get(name)
    if not target:
        raise KeyError(f"{kind} '{name}' not found")
    payload = _base_payload(kind, name)
    if kind == "rag_eval":
        payload.update(
            {
                "pipeline": getattr(target, "pipeline", None),
                "dataset_frame": getattr(target, "dataset_frame", None),
                "metrics": getattr(target, "metrics", None) or [],
            }
        )
    elif kind == "tool_eval":
        payload.update(
            {
                "tool": getattr(target, "tool", None),
                "dataset_frame": getattr(target, "dataset_frame", None),
                "metrics": getattr(target, "metrics", None) or [],
            }
        )
    else:
        payload.update(
            {
                "agent": getattr(target, "agent", None),
                "dataset_frame": getattr(target, "dataset_frame", None),
                "metrics": getattr(target, "metrics", None) or [],
            }
        )
    return payload


def inspect_entity(program: ir.IRProgram, kind: str, name: str) -> dict:
    kind = (kind or "").strip()
    if kind == "app":
        return inspect_app(program, name)
    if kind == "page":
        return inspect_page(program, name)
    if kind == "flow":
        return inspect_flow(program, name)
    if kind == "ai":
        return inspect_ai(program, name)
    if kind == "agent":
        return inspect_agent(program, name)
    if kind == "tool":
        return inspect_tool(program, name)
    if kind == "memory":
        return inspect_memory(program, name)
    if kind == "rag":
        return inspect_rag_pipeline(program, name)
    if kind in {"rag_eval", "tool_eval", "agent_eval"}:
        return inspect_evaluation(program, kind, name)
    raise KeyError(f"Unknown kind '{kind}'")
