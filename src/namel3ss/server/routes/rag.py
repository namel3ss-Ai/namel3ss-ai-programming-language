"""RAG-related API routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from ..deps import Principal, Role, get_principal
from ..schemas import RAGQueryRequest


def build_rag_router(engine_factory) -> APIRouter:
    """Build RAG query and upload routes."""

    router = APIRouter()

    @router.post("/api/rag/query")
    async def api_rag_query(payload: RAGQueryRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            engine = engine_factory(payload.code)
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

    @router.post("/api/rag/upload")
    async def api_rag_upload(
        file: UploadFile = File(...),
        index: str = Form("default"),
        principal: Principal = Depends(get_principal),
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            content_bytes = await file.read()
            try:
                text = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = content_bytes.decode("latin-1", errors="ignore")
            engine = engine_factory("")
            await engine.rag_engine.a_index_documents(index, [text])
            return {"indexed": 1, "index": index}
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router


__all__ = ["build_rag_router"]
