from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence
from uuid import uuid4

from ..ai.embedding_router import EmbeddingRouter
from .retrieval_models import RAGDocument, RetrievalResult
from .vectorstores.base import VectorStore


@dataclass
class RetrievalPipeline:
    embedding_router: EmbeddingRouter
    vector_store: VectorStore
    embedding_model: str = "auto"

    def index(self, documents: Sequence[RAGDocument]) -> None:
        texts = [d.text for d in documents]
        batch = self.embedding_router.embed(texts, model=self.embedding_model)
        self.vector_store.index(documents, embeddings=batch.vectors)

    def retrieve(self, query: str, *, k: int = 5) -> List[RetrievalResult]:
        query_emb = self.embedding_router.embed([query], model=self.embedding_model).vectors[0]
        return self.vector_store.search_results(query_emb, k=k)


def lexical_score(query: str, doc: RAGDocument) -> float:
    q_terms = query.lower().split()
    doc_terms = doc.text.lower().split()
    if not doc_terms:
        return 0.0
    matches = sum(doc_terms.count(t) for t in q_terms)
    return matches / (len(doc_terms) + 1)


@dataclass
class HybridRetrievalPipeline(RetrievalPipeline):
    dense_weight: float = 0.7
    lexical_weight: float = 0.3

    def retrieve(self, query: str, *, k: int = 5) -> List[RetrievalResult]:
        dense_results = super().retrieve(query, k=k)
        # Build lexical candidates from already indexed docs if available
        lexical_candidates: List[RetrievalResult] = []
        if hasattr(self.vector_store, "_items"):
            items = getattr(self.vector_store, "_items")
            for item in items.values():
                doc = RAGDocument(id=item.id, text=item.text, metadata=item.metadata, source=item.source)
                lexical_candidates.append(
                    RetrievalResult(
                        document=doc,
                        score=lexical_score(query, doc),
                        rank=0,
                    )
                )
        merged = {res.document.id: res for res in dense_results}
        for lex in lexical_candidates:
            if lex.document.id in merged:
                merged[lex.document.id] = RetrievalResult(
                    document=lex.document,
                    score=self.dense_weight * merged[lex.document.id].score + self.lexical_weight * lex.score,
                    rank=0,
                )
            else:
                merged[lex.document.id] = RetrievalResult(
                    document=lex.document,
                    score=self.lexical_weight * lex.score,
                    rank=0,
                )
        combined = list(merged.values())
        combined.sort(key=lambda r: r.score, reverse=True)
        for idx, res in enumerate(combined, start=1):
            res.rank = idx
        return combined[:k]
