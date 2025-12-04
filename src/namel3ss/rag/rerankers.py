from __future__ import annotations

from typing import List, Protocol, Sequence

from ..ai.embedding_router import EmbeddingRouter
from .retrieval_models import RetrievalResult
from .vectorstores.memory import _cosine


class Reranker(Protocol):
    def rerank(self, query: str, candidates: Sequence[RetrievalResult]) -> List[RetrievalResult]:
        ...


class NoOpReranker:
    def rerank(self, query: str, candidates: Sequence[RetrievalResult]) -> List[RetrievalResult]:
        results = list(candidates)
        for idx, res in enumerate(results, start=1):
            res.rank = idx
        return results


class EmbeddingReranker:
    """Simple embedding-based reranker using the EmbeddingRouter."""

    def __init__(self, embedding_router: EmbeddingRouter, model: str = "auto") -> None:
        self.embedding_router = embedding_router
        self.model = model

    def rerank(self, query: str, candidates: Sequence[RetrievalResult]) -> List[RetrievalResult]:
        if not candidates:
            return []
        query_emb = self.embedding_router.embed([query], model=self.model).vectors[0]
        rescored: List[RetrievalResult] = []
        for cand in candidates:
            doc_emb = self.embedding_router.embed([cand.document.text], model=self.model).vectors[0]
            score = _cosine(query_emb, doc_emb)
            rescored.append(
                RetrievalResult(
                    document=cand.document,
                    score=score,
                    rank=0,
                    metadata=cand.metadata,
                )
            )
        rescored.sort(key=lambda r: r.score, reverse=True)
        for idx, res in enumerate(rescored, start=1):
            res.rank = idx
        return rescored
