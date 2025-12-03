"""
Model providers for Namel3ss AI runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List


class ModelProvider(ABC):
    """Abstract model provider."""

    def __init__(self, name: str, default_model: str | None = None) -> None:
        self.name = name
        self.default_model = default_model
        self.cost_per_token: float = 0.0
        self.latency_ms: float = 0.0

    @abstractmethod
    def invoke(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        """Invoke the provider with a chat-style messages array."""

    @abstractmethod
    def invoke_stream(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterable[Dict[str, Any]]:
        """Stream responses as an iterable of dict chunks."""


class DummyProvider(ModelProvider):
    """Deterministic provider used for tests/CI."""

    def __init__(self, name: str = "dummy", default_model: str | None = None) -> None:
        super().__init__(name, default_model=default_model or "dummy-model")

    def invoke(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        user_content = messages[-1]["content"] if messages else ""
        return {
            "provider": self.name,
            "model": self.default_model or "dummy-model",
            "messages": messages,
            "result": f"[dummy output from {self.name}] {user_content}".strip(),
            "raw": {"messages": messages},
        }

    def invoke_stream(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterable[Dict[str, Any]]:
        # Simple one-chunk stream for deterministic behavior
        yield self.invoke(messages, **kwargs)
