"""Job scheduling and worker routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..deps import Principal, Role, can_run_flow, get_principal
from ..schemas import RunFlowRequest


def build_jobs_router(scheduler, worker, job_queue) -> APIRouter:
    """Build job/worker endpoints."""

    router = APIRouter()

    @router.post("/api/job/flow")
    def api_job_flow(payload: RunFlowRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_run_flow(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        job = scheduler.schedule_flow(payload.flow, {"code": payload.source})
        return {"job_id": job.id}

    @router.get("/api/job/{job_id}")
    def api_job_status(job_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        job = job_queue.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"job": job.__dict__}

    @router.post("/api/worker/run-once")
    async def api_worker_run_once(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        job = await worker.run_once()
        return {"processed": job.id if job else None}

    @router.get("/api/jobs")
    def api_jobs(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        return {"jobs": [job.__dict__ for job in job_queue.list()]}

    return router


__all__ = ["build_jobs_router"]
