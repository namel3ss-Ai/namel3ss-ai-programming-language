"""
Helpers to describe RAG pipelines for Studio visualizations.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .. import ir


def list_rag_pipelines(program: Any) -> List[str]:
    pipelines = getattr(program, "rag_pipelines", {}) or {}
    return sorted(pipelines.keys())


def describe_rag_pipeline(program: Any, name: str) -> Dict[str, Any]:
    pipelines = getattr(program, "rag_pipelines", {}) or {}
    pipeline: ir.IRRagPipeline | None = pipelines.get(name)
    if pipeline is None:
        raise KeyError(f"rag pipeline '{name}' not found")

    stages_payload: list[dict] = []
    edges: list[dict] = []
    for idx, stage in enumerate(getattr(pipeline, "stages", []) or []):
        data: dict[str, Any] = {
            "name": getattr(stage, "name", f"stage_{idx}"),
            "kind": getattr(stage, "type", None),
            "ai": getattr(stage, "ai", None),
            "vector_store": getattr(stage, "vector_store", None),
            "frame": getattr(stage, "frame", None),
            "graph": getattr(stage, "graph", None),
            "graph_summary": getattr(stage, "graph_summary", None),
            "top_k": _safe_int(stage, "top_k"),
            "max_rows": _safe_int(stage, "max_rows"),
            "max_rows_per_group": _safe_int(stage, "max_rows_per_group"),
            "max_items": _safe_int(stage, "max_items"),
            "max_hops": _safe_int(stage, "max_hops"),
            "max_nodes": _safe_int(stage, "max_nodes"),
            "group_by": getattr(stage, "group_by", None),
            "method": getattr(stage, "method", None),
            "strategy": getattr(stage, "strategy", None),
            "index": idx,
        }
        stages_payload.append(data)
        if idx + 1 < len(getattr(pipeline, "stages", []) or []):
            edges.append({"from": data["name"], "to": getattr(pipeline.stages[idx + 1], "name", f"stage_{idx+1}")})

    return {
        "name": getattr(pipeline, "name", name),
        "default_vector_store": getattr(pipeline, "default_vector_store", None),
        "stages": stages_payload,
        "edges": edges,
    }


def _safe_int(stage: Any, attr: str) -> int | None:
    val = getattr(stage, attr, None)
    if val is None:
        return None
    try:
        return int(val)
    except Exception:
        return None
