from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import List, Optional

from ...distributed.models import Job
from .base import JobStore


class SQLiteJobStore(JobStore):
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    target TEXT,
                    payload TEXT,
                    status TEXT,
                    result TEXT,
                    error TEXT,
                    created_at REAL
                )
                """
            )

    def save_job(self, job: Job) -> Job:
        created_at = time.time()
        with self._connect() as conn:
            existing = conn.execute("SELECT created_at FROM jobs WHERE id = ?", (job.id,)).fetchone()
            created_at = existing[0] if existing else created_at
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (id, type, target, payload, status, result, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.type,
                    job.target,
                    json.dumps(job.payload),
                    job.status,
                    json.dumps(job.result),
                    job.error,
                    created_at,
                ),
            )
        return job

    def dequeue_job(self) -> Optional[Job]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, type, target, payload, status, result, error, created_at
                FROM jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            job = self._row_to_job(row)
            conn.execute("UPDATE jobs SET status = 'running' WHERE id = ?", (job.id,))
            job.status = "running"
            return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, type, target, payload, status, result, error, created_at
                FROM jobs WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_job(row)

    def list_jobs(self) -> List[Job]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, type, target, payload, status, result, error, created_at
                FROM jobs
                """
            ).fetchall()
        return [self._row_to_job(row) for row in rows]

    def update_job(self, job: Job) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, result = ?, error = ?
                WHERE id = ?
                """,
                (job.status, json.dumps(job.result), job.error, job.id),
            )

    def _row_to_job(self, row: tuple) -> Job:
        id_, type_, target, payload_json, status, result_json, error, _created_at = row
        payload = json.loads(payload_json) if payload_json else {}
        result = json.loads(result_json) if result_json else None
        return Job(
            id=id_,
            type=type_,
            target=target,
            payload=payload,
            status=status,
            result=result,
            error=error,
        )
