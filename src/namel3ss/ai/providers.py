"""
Model providers for Namel3ss AI runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class ModelProvider(ABC):
    """Abstract model provider."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.cost_per_token: float = 0.0
        self.latency_ms: float = 0.0

    @abstractmethod
    def invoke(self, prompt: str | None, **kwargs: Any) -> Dict[str, Any]:
        """Invoke the provider with a prompt."""


class DummyProvider(ModelProvider):
    """Stub provider that returns deterministic content."""

    def invoke(self, prompt: str | None, **kwargs: Any) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "prompt": prompt,
            "result": f"[dummy output from {self.name}]",
        }
