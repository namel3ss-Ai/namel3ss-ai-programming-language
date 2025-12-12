from __future__ import annotations

from typing import Any, Callable, Dict

from fastapi import APIRouter, Depends, HTTPException

from ...deps import Principal, Role, get_principal
from ...schemas import RagPreviewRequest, RagStageUpdateRequest


def register_rag_routes(
    router: APIRouter,
    *,
    build_project_engine: Callable[[], Any],
    studio_list_rag_pipelines_fn,
    studio_describe_rag_pipeline_fn,
    metrics_tracker,
    trigger_manager,
    plugin_registry,
) -> None:
    """Register RAG-related Studio routes."""

    def _serialize_rag_stage(stage, idx: int | None = None) -> Dict[str, Any]:
        data = {
            "name": getattr(stage, "name", ""),
            "type": getattr(stage, "type", ""),
            "ai": getattr(stage, "ai", None),
            "vector_store": getattr(stage, "vector_store", None),
            "graph": getattr(stage, "graph", None),
            "graph_summary": getattr(stage, "graph_summary", None),
            "frame": getattr(stage, "frame", None),
            "top_k": getattr(stage, "top_k", None),
            "max_rows": getattr(stage, "max_rows", None),
            "group_by": getattr(stage, "group_by", None),
            "max_rows_per_group": getattr(stage, "max_rows_per_group", None),
            "max_items": getattr(stage, "max_items", None),
            "strategy": getattr(stage, "strategy", None),
            "max_hops": getattr(stage, "max_hops", None),
            "max_nodes": getattr(stage, "max_nodes", None),
        }
        if idx is not None:
            data["index"] = idx
        return data

    def _serialize_rag_pipeline(pipeline) -> Dict[str, Any]:
        stages = [_serialize_rag_stage(st, idx) for idx, st in enumerate(getattr(pipeline, "stages", []))]
        edges = []
        for idx, st in enumerate(stages):
            if idx + 1 < len(stages):
                edges.append({"from": stages[idx]["name"], "to": stages[idx + 1]["name"]})
        return {
            "name": getattr(pipeline, "name", ""),
            "default_vector_store": getattr(pipeline, "default_vector_store", None),
            "stages": stages,
            "edges": edges,
        }

    @router.get("/api/studio/rag/list")
    def api_studio_rag_list() -> Dict[str, Any]:
        return studio_list_rag_pipelines_fn()

    @router.get("/api/studio/rag/pipeline")
    def api_studio_rag_pipeline(name: str) -> Dict[str, Any]:
        return studio_describe_rag_pipeline_fn(name)

    @router.get("/api/studio/rag/pipelines")
    def api_studio_rag_pipelines(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = build_project_engine()
        except Exception:
            from ....runtime.engine import Engine  # local import to avoid cycles

            engine = Engine.from_source(
                "",
                metrics_tracker=metrics_tracker,
                trigger_manager=trigger_manager,
                plugin_registry=plugin_registry,
            )
        pipelines = [
            {"id": name, "name": name, "description": "", "source": None}
            for name in (getattr(engine.program, "rag_pipelines", {}) or {}).keys()
        ]
        return {"pipelines": pipelines}

    @router.get("/api/studio/rag/pipelines/{pipeline_id}")
    def api_studio_rag_pipeline_detail(
        pipeline_id: str, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = build_project_engine()
        pipeline = (getattr(engine.program, "rag_pipelines", {}) or {}).get(pipeline_id)
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        return {"pipeline": _serialize_rag_pipeline(pipeline)}

    @router.post("/api/studio/rag/pipelines/{pipeline_id}/update_stage")
    def api_studio_rag_update_stage(
        pipeline_id: str, payload: RagStageUpdateRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = build_project_engine()
        pipeline = (getattr(engine.program, "rag_pipelines", {}) or {}).get(pipeline_id)
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        stage_name = payload.stage
        changes = payload.changes or {}
        stage = next((st for st in pipeline.stages if getattr(st, "name", None) == stage_name), None)
        if not stage:
            raise HTTPException(status_code=404, detail="Stage not found")
        allowed_fields = {
            "ai",
            "vector_store",
            "graph",
            "graph_summary",
            "frame",
            "match_column",
            "max_rows",
            "group_by",
            "max_rows_per_group",
            "max_items",
            "strategy",
            "max_hops",
            "max_nodes",
            "top_k",
            "method",
            "embedding_model",
            "output_vector_store",
            "image_column",
            "text_column",
        }
        for key, value in changes.items():
            if key in allowed_fields:
                setattr(stage, key, value)
        return {"status": "updated", "stage": _serialize_rag_stage(stage), "pipeline": _serialize_rag_pipeline(pipeline)}

    @router.post("/api/studio/rag/pipelines/{pipeline_id}/preview")
    def api_studio_rag_preview(
        pipeline_id: str, payload: RagPreviewRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = build_project_engine()
        pipeline = (getattr(engine.program, "rag_pipelines", {}) or {}).get(pipeline_id)
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        query = payload.query
        stage_previews: list[dict[str, Any]] = []
        for st in pipeline.stages:
            stage_previews.append(
                {
                    "stage": st.name,
                    "type": st.type,
                    "summary": f"Configured stage {st.name} ({st.type})",
                    "params": {k: v for k, v in _serialize_rag_stage(st).items() if k not in {"name", "type"}},
                }
            )
        return {"pipeline": _serialize_rag_pipeline(pipeline), "query": query, "stages": stage_previews}


__all__ = ["register_rag_routes"]
