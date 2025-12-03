from __future__ import annotations

from typing import List, Protocol

from ..models import RAGItem, ScoredItem


class VectorQueryResult(ScoredItem):
    ...


class VectorStore(Protocol):
    async def a_add(self, items: List[RAGItem]) -> None:
        ...

    async def a_query(self, query_embedding: List[float], k: int = 10) -> List[ScoredItem]:
        ...

    async def a_delete(self, ids: List[str]) -> None:
        ...
