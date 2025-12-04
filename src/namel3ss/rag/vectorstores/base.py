from __future__ import annotations

from typing import List, Protocol, Sequence

from ..models import RAGItem, ScoredItem
from ..retrieval_models import RAGDocument, RetrievalResult


class VectorStore(Protocol):
    def add_sync(self, items: List[RAGItem]) -> None:
        ...

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[ScoredItem]:
        ...

    async def a_add(self, items: List[RAGItem]) -> None:
        ...

    async def a_query(self, query_embedding: List[float], k: int = 10) -> List[ScoredItem]:
        ...

    # New structured interfaces for retrieval pipelines
    def index(self, documents: Sequence[RAGDocument], *, embeddings: Sequence[List[float]] | None = None) -> None:
        ...

    def search_results(self, query_embedding: List[float], *, k: int = 5) -> List[RetrievalResult]:
        ...
