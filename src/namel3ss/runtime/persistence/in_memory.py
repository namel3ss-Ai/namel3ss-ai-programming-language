from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Optional

from ...distributed.models import Job
from .base import JobStore


class InMemoryJobStore(JobStore):
    def __init__(self) -> None:
        self._queue: Deque[Job] = deque()
        self._jobs: Dict[str, Job] = {}

    def save_job(self, job: Job) -> Job:
        self._queue.append(job)
        self._jobs[job.id] = job
        return job

    def dequeue_job(self) -> Optional[Job]:
        if not self._queue:
            return None
        job = self._queue.popleft()
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[Job]:
        return list(self._jobs.values())

    def update_job(self, job: Job) -> None:
        self._jobs[job.id] = job
