"""Embedding abstractions and providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Protocol, Sequence


@dataclass(frozen=True)
class EmbeddingResult:
    vector: List[float]
    dim: int
    model_name: str
    raw: Optional[Any] = None


@dataclass(frozen=True)
class EmbeddingBatchResult:
    vectors: List[List[float]]
    dim: int
    model_name: str
    raw: Optional[Any] = None


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str], *, model: str | None = None, **kwargs: Any) -> EmbeddingBatchResult:
        ...


class DeterministicEmbeddingProvider:
    """Deterministic, seedless embedding provider for CI/tests."""

    def __init__(self, dimensions: int = 8, model: str | None = None) -> None:
        self.dimensions = dimensions
        self.model = model or f"det-{dimensions}"
        self.name = "deterministic"

    def _embed_one(self, text: str) -> List[float]:
        vector = [0.0 for _ in range(self.dimensions)]
        for idx, ch in enumerate(text):
            vector[idx % self.dimensions] += (ord(ch) % 97) / 100.0
        return vector

    def embed(self, texts: Sequence[str], *, model: str | None = None, **kwargs: Any) -> EmbeddingBatchResult:
        vectors = [self._embed_one(t) for t in texts]
        return EmbeddingBatchResult(vectors=vectors, dim=self.dimensions, model_name=model or self.model, raw=None)

    # Compatibility helpers for legacy interfaces
    def embed_text(self, text: str, **kwargs: Any) -> List[float]:
        return self._embed_one(text)

    def embed_batch(self, texts: Sequence[str], **kwargs: Any) -> List[List[float]]:
        return [self._embed_one(t) for t in texts]
