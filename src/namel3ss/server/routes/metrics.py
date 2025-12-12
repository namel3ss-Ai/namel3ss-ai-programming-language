"""Metrics endpoint routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..deps import Principal, Role, get_principal


def build_metrics_router(metrics_tracker) -> APIRouter:
    router = APIRouter()

    @router.get("/api/metrics")
    def api_metrics(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"metrics": metrics_tracker.snapshot()}

    return router


__all__ = ["build_metrics_router"]
