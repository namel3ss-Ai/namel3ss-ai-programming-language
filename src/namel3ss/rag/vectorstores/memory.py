from __future__ import annotations

import math
from typing import Dict, List, Sequence

from ..models import RAGItem, ScoredItem
from ..retrieval_models import RAGDocument, RetrievalResult
from .base import VectorStore


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._items: Dict[str, RAGItem] = {}

    async def a_add(self, items: List[RAGItem]) -> None:
        for item in items:
            self._items[item.id] = item

    async def a_query(self, query_embedding: List[float], k: int = 10) -> List[ScoredItem]:
        scored: List[ScoredItem] = []
        for item in self._items.values():
            if not item.embedding:
                continue
            score = _cosine(query_embedding, item.embedding)
            scored.append(ScoredItem(item=item, score=score, source=item.source or "memory"))
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:k]

    async def a_delete(self, ids: List[str]) -> None:
        for id_ in ids:
            self._items.pop(id_, None)

    def all_items(self) -> List[RAGItem]:
        return list(self._items.values())

    def add_sync(self, items: List[RAGItem]) -> None:
        for item in items:
            self._items[item.id] = item

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[ScoredItem]:
        # synchronous helper for backwards compatibility
        scored: List[ScoredItem] = []
        for item in self._items.values():
            if not item.embedding:
                continue
            score = _cosine(query_embedding, item.embedding)
            scored.append(ScoredItem(item=item, score=score, source=item.source or "memory"))
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]

    # Structured API for new retrieval pipeline
    def index(self, documents: Sequence[RAGDocument], *, embeddings: Sequence[List[float]] | None = None) -> None:
        if embeddings is None:
            raise ValueError("embeddings are required for indexing in InMemoryVectorStore")
        if len(documents) != len(embeddings):
            raise ValueError("documents and embeddings length mismatch")
        items: List[RAGItem] = []
        for doc, emb in zip(documents, embeddings):
            items.append(
                RAGItem(
                    id=doc.id,
                    text=doc.text,
                    metadata=doc.metadata,
                    embedding=emb,
                    source=doc.source,
                )
            )
        self.add_sync(items)

    def search_results(self, query_embedding: List[float], *, k: int = 5) -> List[RetrievalResult]:
        scored = self.search(query_embedding, top_k=k)
        results: List[RetrievalResult] = []
        for rank, sc in enumerate(scored, start=1):
            doc = RAGDocument(id=sc.item.id, text=sc.item.text, metadata=sc.item.metadata, source=sc.item.source)
            results.append(RetrievalResult(document=doc, score=sc.score, rank=rank))
        return results
