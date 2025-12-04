"""
Embedding provider base interface.
"""

from __future__ import annotations

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Sequence

from ..ai.embedding_router import EmbeddingRouter
from ..ai.embeddings import EmbeddingBatchResult


class EmbeddingProvider(ABC):
    def __init__(self, name: str, model: str | None = None) -> None:
        self.name = name
        self.model = model or "deterministic"

    @abstractmethod
    def embed_text(self, text: str, **kwargs) -> List[float]:
        ...

    @abstractmethod
    def embed_batch(self, texts: List[str], **kwargs) -> List[List[float]]:
        ...


class RouterEmbeddingProvider(EmbeddingProvider):
    """Adapter that delegates to the new AI embedding router while preserving legacy API."""

    def __init__(self, router: EmbeddingRouter, model: str | None = None) -> None:
        super().__init__("router", model=model)
        self.router = router

    def _run(self, texts: Sequence[str]) -> EmbeddingBatchResult:
        return self.router.embed(texts, model=self.model)

    def embed_text(self, text: str, **kwargs) -> List[float]:
        return self._run([text]).vectors[0]

    def embed_batch(self, texts: List[str], **kwargs) -> List[List[float]]:
        return self._run(texts).vectors
