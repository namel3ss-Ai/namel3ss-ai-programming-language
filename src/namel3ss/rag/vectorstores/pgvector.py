from __future__ import annotations

from typing import List

try:
    import psycopg  # type: ignore
except Exception:  # pragma: no cover
    psycopg = None

from ..models import RAGItem, ScoredItem
from .base import VectorStore
from ...errors import Namel3ssError


class PGVectorStore(VectorStore):
    def __init__(self, dsn: str, table: str = "rag_items") -> None:
        if psycopg is None:
            raise Namel3ssError("psycopg/pgvector not installed; cannot use pgvector backend")
        if not dsn:
            raise Namel3ssError("PGVector backend requested but DSN not set")
        self.dsn = dsn
        self.table = table
        self._ensure_table()

    def _ensure_table(self) -> None:
        with psycopg.connect(self.dsn) as conn:  # pragma: no cover - env dependent
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    id TEXT PRIMARY KEY,
                    text TEXT,
                    metadata JSONB,
                    embedding VECTOR
                )
                """
            )
            conn.commit()

    async def a_add(self, items: List[RAGItem]) -> None:
        with psycopg.connect(self.dsn) as conn:  # pragma: no cover - env dependent
            for item in items:
                conn.execute(
                    f"INSERT INTO {self.table} (id, text, metadata, embedding) VALUES (%s, %s, %s, %s) "
                    f"ON CONFLICT (id) DO UPDATE SET text = EXCLUDED.text, metadata = EXCLUDED.metadata, embedding = EXCLUDED.embedding",
                    (item.id, item.text, item.metadata, item.embedding),
                )
            conn.commit()

    async def a_query(self, query_embedding: List[float], k: int = 10) -> List[ScoredItem]:
        with psycopg.connect(self.dsn) as conn:  # pragma: no cover - env dependent
            rows = conn.execute(
                f"SELECT id, text, metadata, 1 - (embedding <=> %s) as score FROM {self.table} "
                f"ORDER BY embedding <=> %s LIMIT %s",
                (query_embedding, query_embedding, k),
            ).fetchall()
        scored: List[ScoredItem] = []
        for row in rows:
            item = RAGItem(id=row[0], text=row[1], metadata=row[2] or {}, embedding=None, source="pgvector")
            scored.append(ScoredItem(item=item, score=float(row[3]), source="pgvector"))
        return scored

    def add_sync(self, items: List[RAGItem]) -> None:
        # delegate to async implementation
        import asyncio

        asyncio.run(self.a_add(items))

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[ScoredItem]:
        import asyncio

        return asyncio.run(self.a_query(query_embedding, k=top_k))

    async def a_delete(self, ids: List[str]) -> None:
        with psycopg.connect(self.dsn) as conn:  # pragma: no cover - env dependent
            conn.execute(
                f"DELETE FROM {self.table} WHERE id = ANY(%s)",
                (ids,),
            )
            conn.commit()
