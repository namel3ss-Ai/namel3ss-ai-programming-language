from __future__ import annotations

from typing import Dict, List

from .base import VectorStore
from ..models import RAGItem, ScoredItem
from ...errors import Namel3ssError

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None


class FAISSVectorStore(VectorStore):
    def __init__(self, dimension: int) -> None:
        if faiss is None:
            raise Namel3ssError("faiss not installed; cannot use FAISS backend")
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        self._items: Dict[int, RAGItem] = {}
        self._next_id = 0

    def add_sync(self, items: List[RAGItem]) -> None:
        vectors = []
        ids = []
        for item in items:
            if not item.embedding:
                continue
            if len(item.embedding) != self.dimension:
                raise Namel3ssError("Embedding dimension mismatch for FAISS index")
            vectors.append(item.embedding)
            ids.append(self._next_id)
            self._items[self._next_id] = item
            self._next_id += 1
        if vectors:
            import numpy as np  # type: ignore

            arr = np.array(vectors, dtype="float32")
            self.index.add(arr)

    async def a_add(self, items: List[RAGItem]) -> None:
        self.add_sync(items)

    async def a_query(self, query_embedding: List[float], k: int = 10) -> List[ScoredItem]:
        import numpy as np  # type: ignore

        if len(query_embedding) != self.dimension:
            raise Namel3ssError("Query embedding dimension mismatch for FAISS index")
        if self.index.ntotal == 0:
            return []
        arr = np.array([query_embedding], dtype="float32")
        scores, indices = self.index.search(arr, k)
        results: List[ScoredItem] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            item = self._items.get(int(idx))
            if item:
                results.append(ScoredItem(item=item, score=float(score), source=item.source or "faiss"))
        return results

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[ScoredItem]:
        import asyncio

        return asyncio.run(self.a_query(query_embedding, k=top_k))
