from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from ..models import MemoryItem, MemoryType
from .base import MemoryStore


class SQLiteMemoryStore(MemoryStore):
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    id TEXT PRIMARY KEY,
                    space TEXT,
                    type TEXT,
                    content TEXT,
                    metadata TEXT
                )
                """
            )

    def add(self, item: MemoryItem) -> MemoryItem:
        metadata_json = json.dumps(item.metadata or {})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_items (id, space, type, content, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (item.id, item.space, item.type.value if hasattr(item.type, "value") else str(item.type), item.content, metadata_json),
            )
        return item

    def list(self, space: Optional[str] = None) -> List[MemoryItem]:
        query = "SELECT id, space, type, content, metadata FROM memory_items"
        params = ()
        if space is not None:
            query += " WHERE space = ?"
            params = (space,)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_item(row) for row in rows]

    def query(self, space: str, text: str) -> List[MemoryItem]:
        like = f"%{text}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, space, type, content, metadata FROM memory_items
                WHERE space = ? AND content LIKE ?
                """,
                (space, like),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def clear_space(self, space: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM memory_items WHERE space = ?", (space,))

    def _row_to_item(self, row: tuple) -> MemoryItem:
        id_, space, typ, content, metadata_json = row
        metadata = json.loads(metadata_json) if metadata_json else {}
        mem_type = MemoryType(typ) if typ in MemoryType._value2member_map_ else MemoryType.CONVERSATION
        return MemoryItem(
            id=id_,
            space=space,
            type=mem_type,
            content=content,
            metadata=metadata,
        )
