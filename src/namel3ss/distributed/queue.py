"""
Job queue abstraction with pluggable persistence.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from ..secrets.manager import SecretsManager
from ..runtime.persistence import InMemoryJobStore, SQLiteJobStore
from .models import Job


class JobQueue:
    def __init__(self, store=None) -> None:
        self.store = store or InMemoryJobStore()

    def enqueue(self, job: Job) -> Job:
        return self.store.save_job(job)

    def create_and_enqueue(self, type: str, target: str, payload: Optional[dict] = None) -> Job:
        job = Job(id=str(uuid4()), type=type, target=target, payload=payload or {})
        return self.enqueue(job)

    def dequeue(self) -> Optional[Job]:
        return self.store.dequeue_job()

    def get(self, job_id: str) -> Optional[Job]:
        return self.store.get_job(job_id)

    def list(self) -> List[Job]:
        return self.store.list_jobs()

    def update(self, job: Job) -> None:
        self.store.update_job(job)


def _build_default_queue() -> JobQueue:
    secrets = SecretsManager()
    if secrets.is_enabled("N3_ENABLE_PERSISTENT_JOBS"):
        db_path = secrets.get("N3_JOBS_DB_PATH") or "namel3ss_jobs.db"
        store = SQLiteJobStore(db_path)
        return JobQueue(store=store)
    return JobQueue()


global_job_queue = _build_default_queue()
