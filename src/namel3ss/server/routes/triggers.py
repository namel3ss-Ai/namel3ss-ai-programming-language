"""Flow trigger endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..deps import Principal, Role, can_run_flow, get_principal
from ..schemas import TriggerFireRequest, TriggerRegistrationRequest


def build_triggers_router(trigger_manager, flow_trigger_cls) -> APIRouter:
    """Build the triggers router."""

    router = APIRouter()

    @router.get("/api/flows/triggers")
    async def api_list_triggers(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        triggers = await trigger_manager.a_list_triggers()
        return {
            "triggers": [
                {
                    "id": t.id,
                    "kind": t.kind,
                    "flow_name": t.flow_name,
                    "config": t.config,
                    "enabled": t.enabled,
                    "last_fired": t.last_fired.isoformat() if t.last_fired else None,
                    "next_fire_at": t.next_fire_at.isoformat() if t.next_fire_at else None,
                }
                for t in triggers
            ]
        }

    @router.post("/api/flows/triggers")
    async def api_register_trigger(
        payload: TriggerRegistrationRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        trigger = flow_trigger_cls(
            id=payload.id,
            kind=payload.kind,
            flow_name=payload.flow_name,
            config=payload.config,
            enabled=payload.enabled,
        )
        await trigger_manager.a_register_trigger(trigger)
        return {"trigger": trigger.__dict__}

    @router.post("/api/flows/trigger/{trigger_id}")
    async def api_fire_trigger(
        trigger_id: str, payload: TriggerFireRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        job = await trigger_manager.a_fire_trigger(trigger_id, payload.payload or {})
        return {"job_id": job.id if job else None}

    @router.post("/api/flows/triggers/tick")
    async def api_tick_triggers(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        fired = await trigger_manager.a_tick_schedules()
        return {"fired": [job.id for job in fired]}

    return router


__all__ = ["build_triggers_router"]
