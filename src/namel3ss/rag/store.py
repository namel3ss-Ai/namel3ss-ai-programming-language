"""
Legacy helpers for deterministic embeddings (compatibility).
"""

from __future__ import annotations

import math
from typing import List

from .embeddings_deterministic import DeterministicEmbeddingProvider
from .models import DocumentChunk


def embed_text(text: str, dimensions: int = 8) -> List[float]:
    """Deterministic naive embedding kept for compatibility."""

    provider = DeterministicEmbeddingProvider(dimensions=dimensions)
    return provider.embed_text(text)


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._chunks: List[DocumentChunk] = []

    def add(self, chunk: DocumentChunk) -> None:
        self._chunks.append(chunk)

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[DocumentChunk]:
        scored = [
            (chunk, _cosine(query_embedding, chunk.embedding or [0.0 for _ in query_embedding]))
            for chunk in self._chunks
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [chunk for chunk, _score in scored[:top_k]]
