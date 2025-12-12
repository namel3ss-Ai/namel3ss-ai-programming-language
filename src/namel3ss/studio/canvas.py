"""
Canvas manifest builder for Studio.

Produces a read-only map of program entities (apps, pages, flows, agents, tools, memory, rag, evaluations)
and the relationships between them. This relies solely on IR and does not mutate any state.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List

from .. import ir


def _node_id(kind: str, name: str) -> str:
    return f"{kind}:{name}"


def build_canvas_manifest(program: ir.IRProgram | None) -> dict:
    if program is None:
        return {"nodes": [], "edges": [], "status": "empty"}

    nodes: List[dict] = []
    edges: List[dict] = []

    # Apps
    for app_name, app in (getattr(program, "apps", {}) or {}).items():
        nodes.append({"id": _node_id("app", app_name), "kind": "app", "name": app_name, "entry_page": getattr(app, "entry_page", None)})
        if getattr(app, "entry_page", None):
            edges.append({"from": _node_id("app", app_name), "to": _node_id("page", app.entry_page), "kind": "entry_page"})

    # Pages
    for page_name, page in (getattr(program, "pages", {}) or {}).items():
        nodes.append(
            {
                "id": _node_id("page", page_name),
                "kind": "page",
                "name": page_name,
                "route": getattr(page, "route", None),
            }
        )
        for ai_name in getattr(page, "ai_calls", []) or []:
            edges.append({"from": _node_id("page", page_name), "to": _node_id("ai", ai_name), "kind": "ai_ref"})
        for agent_name in getattr(page, "agents", []) or []:
            edges.append({"from": _node_id("page", page_name), "to": _node_id("agent", agent_name), "kind": "agent_ref"})
        for mem_name in getattr(page, "memories", []) or []:
            edges.append({"from": _node_id("page", page_name), "to": _node_id("memory", mem_name), "kind": "memory_ref"})

    # Flows
    for flow_name, flow in (getattr(program, "flows", {}) or {}).items():
        nodes.append({"id": _node_id("flow", flow_name), "kind": "flow", "name": flow_name})
        for step in getattr(flow, "steps", []) or []:
            kind = getattr(step, "kind", None)
            target = getattr(step, "target", None)
            if kind in {"ai", "agent", "tool", "goto_flow"} and target:
                edges.append({"from": _node_id("flow", flow_name), "to": _node_id(kind if kind != "goto_flow" else "flow", target), "kind": f"{kind}_step"})

    # AI calls
    for ai_name, ai_call in (getattr(program, "ai_calls", {}) or {}).items():
        nodes.append({"id": _node_id("ai", ai_name), "kind": "ai", "name": ai_name, "model": getattr(ai_call, "model_name", None)})
        if getattr(ai_call, "model_name", None):
            edges.append({"from": _node_id("ai", ai_name), "to": _node_id("model", ai_call.model_name), "kind": "model"})
        if getattr(ai_call, "memory_name", None):
            edges.append({"from": _node_id("ai", ai_name), "to": _node_id("memory", ai_call.memory_name), "kind": "memory"})
        for tool_binding in getattr(ai_call, "tools", []) or []:
            target_tool = getattr(tool_binding, "internal_name", None) or getattr(tool_binding, "exposed_name", None)
            if target_tool:
                edges.append({"from": _node_id("ai", ai_name), "to": _node_id("tool", target_tool), "kind": "tool"})

    # Agents
    for agent_name, agent in (getattr(program, "agents", {}) or {}).items():
        nodes.append({"id": _node_id("agent", agent_name), "kind": "agent", "name": agent_name})
        if getattr(agent, "memory_name", None):
            edges.append({"from": _node_id("agent", agent_name), "to": _node_id("memory", agent.memory_name), "kind": "memory"})

    # Tools
    for tool_name, tool in (getattr(program, "tools", {}) or {}).items():
        nodes.append({"id": _node_id("tool", tool_name), "kind": "tool", "name": tool_name, "tool_kind": getattr(tool, "kind", None)})

    # Models
    for model_name, model in (getattr(program, "models", {}) or {}).items():
        nodes.append({"id": _node_id("model", model_name), "kind": "model", "name": model_name, "provider": getattr(model, "provider", None)})

    # Memories
    for mem_name, mem in (getattr(program, "memories", {}) or {}).items():
        nodes.append({"id": _node_id("memory", mem_name), "kind": "memory", "name": mem_name, "memory_type": getattr(mem, "memory_type", None)})

    # RAG
    for pipeline_name, pipeline in (getattr(program, "rag_pipelines", {}) or {}).items():
        nodes.append({"id": _node_id("rag", pipeline_name), "kind": "rag", "name": pipeline_name})
        if getattr(pipeline, "default_vector_store", None):
            edges.append({"from": _node_id("rag", pipeline_name), "to": _node_id("vector_store", pipeline.default_vector_store), "kind": "vector_store"})
    for store_name in (getattr(program, "vector_stores", {}) or {}):
        nodes.append({"id": _node_id("vector_store", store_name), "kind": "vector_store", "name": store_name})

    # Evaluations
    for eval_name, rag_eval in (getattr(program, "rag_evaluations", {}) or {}).items():
        nodes.append({"id": _node_id("rag_eval", eval_name), "kind": "rag_eval", "name": eval_name})
        edges.append({"from": _node_id("rag_eval", eval_name), "to": _node_id("rag", rag_eval.pipeline), "kind": "pipeline"})
    for eval_name, tool_eval in (getattr(program, "tool_evaluations", {}) or {}).items():
        nodes.append({"id": _node_id("tool_eval", eval_name), "kind": "tool_eval", "name": eval_name})
        edges.append({"from": _node_id("tool_eval", eval_name), "to": _node_id("tool", tool_eval.tool), "kind": "tool"})
    for eval_name, agent_eval in (getattr(program, "agent_evaluations", {}) or {}).items():
        nodes.append({"id": _node_id("agent_eval", eval_name), "kind": "agent_eval", "name": eval_name})
        edges.append({"from": _node_id("agent_eval", eval_name), "to": _node_id("agent", agent_eval.agent), "kind": "agent"})

    return {"nodes": nodes, "edges": edges, "status": "ok"}

