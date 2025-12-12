"""Optimizer-related API routes."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..deps import Principal, Role, get_principal


def build_optimizer_router(
    optimizer_storage,
    overlay_store,
    get_default_secrets_manager,
    tracer_cls,
    optimizer_engine_cls,
    suggestion_applier_cls,
    metrics_tracker,
) -> APIRouter:
    """Build optimizer routes."""

    router = APIRouter()

    @router.get("/api/optimizer/suggestions")
    def api_optimizer_suggestions(status: Optional[str] = None, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        storage = optimizer_storage
        from namel3ss.optimizer.models import OptimizationStatus

        stat = OptimizationStatus(status) if status else None
        suggestions = storage.list(stat)
        return {"suggestions": [s.__dict__ for s in suggestions]}

    @router.post("/api/optimizer/scan")
    def api_optimizer_scan(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = optimizer_engine_cls(
            storage=optimizer_storage,
            metrics=metrics_tracker,
            memory_engine=None,
            tracer=tracer_cls(),
            router=None,
            secrets=get_default_secrets_manager(),
        )
        suggestions = engine.scan()
        return {"created": [s.id for s in suggestions]}

    @router.post("/api/optimizer/apply/{suggestion_id}")
    def api_optimizer_apply(suggestion_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        sugg = optimizer_storage.get(suggestion_id)
        if not sugg:
            raise HTTPException(status_code=404, detail="Not found")
        applier = suggestion_applier_cls(overlay_store, optimizer_storage, tracer=tracer_cls())
        applier.apply(sugg)
        return {"status": "applied"}

    @router.post("/api/optimizer/reject/{suggestion_id}")
    def api_optimizer_reject(suggestion_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        sugg = optimizer_storage.get(suggestion_id)
        if not sugg:
            raise HTTPException(status_code=404, detail="Not found")
        from namel3ss.optimizer.models import OptimizationStatus

        sugg.status = OptimizationStatus.REJECTED
        optimizer_storage.update(sugg)
        return {"status": "rejected"}

    @router.get("/api/optimizer/overlays")
    def api_optimizer_overlays(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"overlays": overlay_store.load().to_dict()}

    return router


__all__ = ["build_optimizer_router"]
