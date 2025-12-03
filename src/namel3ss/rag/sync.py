"""
RAG sync worker for ingesting memory into vector store.
"""

from __future__ import annotations

from typing import List, Optional

from .engine import RAGEngine
from ..memory.engine import MemoryEngine


class RAGSyncWorker:
    def __init__(self, memory_engine: MemoryEngine, rag_engine: RAGEngine) -> None:
        self.memory_engine = memory_engine
        self.rag_engine = rag_engine

    async def run_once(self, space: Optional[str] = None) -> None:
        spaces = [space] if space else list(self.memory_engine.spaces.keys())
        for sp in spaces:
            items = []
            if hasattr(self.memory_engine, "list_all"):
                items = self.memory_engine.list_all(sp)
            else:
                items = self.memory_engine.get_recent(sp, limit=1000)
            texts: List[str] = [item.content for item in items]
            if texts:
                index_name = getattr(self.rag_engine, "_default_index", "default")
                self.rag_engine.index_documents(index_name=index_name, texts=texts)

    async def run_forever(self, poll_interval: float = 1.0) -> None:
        import asyncio

        while True:
            await self.run_once()
            await asyncio.sleep(poll_interval)
