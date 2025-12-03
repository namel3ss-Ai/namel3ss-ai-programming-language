"""
Worker loop to process jobs.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

from ..obs.tracer import Tracer
from .models import Job
from .queue import JobQueue


class Worker:
    def __init__(
        self,
        runtime_factory: Callable[[str | None], object],
        job_queue: JobQueue,
        tracer: Optional[Tracer] = None,
        worker_id: str = "worker-1",
    ) -> None:
        self.runtime_factory = runtime_factory
        self.job_queue = job_queue
        self.tracer = tracer
        self.worker_id = worker_id
        self.processed_jobs = 0

    async def run_once(self) -> Optional[Job]:
        job = self.job_queue.dequeue()
        if not job:
            return None
        job.status = "running"
        runtime = self.runtime_factory(job.payload.get("code") if job.payload else None)
        try:
            result = await self._execute_job(runtime, job)
            job.result = result
            job.status = "success"
        except Exception as exc:  # pragma: no cover - error path
            job.error = str(exc)
            job.status = "error"
        self.job_queue.update(job)
        self.processed_jobs += 1
        return job

    async def run_forever(self, poll_interval: float = 0.1) -> None:
        while True:
            job = await self.run_once()
            if not job:
                await asyncio.sleep(poll_interval)

    async def _execute_job(self, runtime, job: Job):
        if job.type == "flow":
            return await runtime.a_execute_flow(job.target, payload=job.payload)
        if job.type == "agent":
            return runtime.execute_agent(job.target)
        if job.type == "page":
            return runtime.execute_page_public(job.target)
        if job.type == "tool":
            tool = runtime.tool_registry.get(job.target)
            if not tool:
                raise ValueError(f"Tool '{job.target}' not found")
            return tool.run(**job.payload)
        raise ValueError(f"Unknown job type '{job.type}'")
