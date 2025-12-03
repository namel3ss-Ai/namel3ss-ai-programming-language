"""
Embedding provider base interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


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
