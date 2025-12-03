"""
Deterministic embedding provider for CI/tests.
"""

from __future__ import annotations

from typing import List

from .embeddings import EmbeddingProvider


class DeterministicEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimensions: int = 8) -> None:
        super().__init__("deterministic", model=f"det-{dimensions}")
        self.dimensions = dimensions

    def _embed(self, text: str) -> List[float]:
        vector = [0.0 for _ in range(self.dimensions)]
        for idx, ch in enumerate(text):
            vector[idx % self.dimensions] += (ord(ch) % 97) / 100.0
        return vector

    def embed_text(self, text: str, **kwargs) -> List[float]:
        return self._embed(text)

    def embed_batch(self, texts: List[str], **kwargs) -> List[List[float]]:
        return [self._embed(t) for t in texts]
