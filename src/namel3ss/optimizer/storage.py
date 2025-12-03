"""
Persistence for optimization suggestions.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from .models import OptimizationSuggestion, OptimizationStatus, OptimizationKind


class OptimizerStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS suggestions (
                id TEXT PRIMARY KEY,
                kind TEXT,
                created_at TEXT,
                status TEXT,
                severity TEXT,
                title TEXT,
                description TEXT,
                reason TEXT,
                target TEXT,
                actions TEXT,
                metrics_snapshot TEXT
            )
            """
        )
        conn.commit()
        conn.close()

    def save(self, suggestion: OptimizationSuggestion) -> None:
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO suggestions (id, kind, created_at, status, severity, title, description, reason, target, actions, metrics_snapshot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                suggestion.id,
                suggestion.kind.value,
                suggestion.created_at.isoformat(),
                suggestion.status.value,
                suggestion.severity,
                suggestion.title,
                suggestion.description,
                suggestion.reason,
                json.dumps(suggestion.target),
                json.dumps(suggestion.actions),
                json.dumps(suggestion.metrics_snapshot),
            ),
        )
        conn.commit()
        conn.close()

    def update(self, suggestion: OptimizationSuggestion) -> None:
        conn = self._connect()
        conn.execute(
            """
            UPDATE suggestions SET status=?, actions=?, metrics_snapshot=? WHERE id=?
            """,
            (
                suggestion.status.value,
                json.dumps(suggestion.actions),
                json.dumps(suggestion.metrics_snapshot),
                suggestion.id,
            ),
        )
        conn.commit()
        conn.close()

    def get(self, suggestion_id: str) -> Optional[OptimizationSuggestion]:
        conn = self._connect()
        cur = conn.execute("SELECT * FROM suggestions WHERE id=?", (suggestion_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_suggestion(row)

    def list(self, status: Optional[OptimizationStatus] = None) -> List[OptimizationSuggestion]:
        conn = self._connect()
        if status:
            cur = conn.execute("SELECT * FROM suggestions WHERE status=?", (status.value,))
        else:
            cur = conn.execute("SELECT * FROM suggestions")
        rows = cur.fetchall()
        conn.close()
        return [self._row_to_suggestion(r) for r in rows]

    def _row_to_suggestion(self, row: tuple) -> OptimizationSuggestion:
        _, kind, created_at, status, severity, title, description, reason, target, actions, metrics_snapshot = row
        return OptimizationSuggestion(
            id=row[0],
            kind=OptimizationKind(kind),
            created_at=self._parse_dt(created_at),
            status=OptimizationStatus(status),
            severity=severity,
            title=title,
            description=description,
            reason=reason,
            target=json.loads(target),
            actions=json.loads(actions),
            metrics_snapshot=json.loads(metrics_snapshot),
        )

    @staticmethod
    def _parse_dt(value: str):
        from datetime import datetime

        return datetime.fromisoformat(value)
