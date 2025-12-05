from __future__ import annotations

from typing import List, Optional, Protocol

from ...distributed.models import Job


class JobStore(Protocol):
    def save_job(self, job: Job) -> Job:
        ...

    def dequeue_job(self) -> Optional[Job]:
        ...

    def get_job(self, job_id: str) -> Optional[Job]:
        ...

    def list_jobs(self) -> List[Job]:
        ...

    def update_job(self, job: Job) -> None:
        ...
