"""Model provider abstractions and built-in providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, TypedDict

from ..models import ModelResponse, ModelStreamChunk


class ToolSchema(TypedDict, total=False):
    name: str
    description: Optional[str]
    parameters: Dict[str, Any]


class ToolCallResult(TypedDict, total=False):
    name: str
    arguments: Dict[str, Any]


@dataclass
class ChatToolResponse:
    final_text: Optional[str]
    tool_calls: List[ToolCallResult]
    raw: Any | None = None
    finish_reason: Optional[str] = None


class ModelProvider(ABC):
    """Abstract model provider."""

    def __init__(self, name: str, default_model: str | None = None) -> None:
        self.name = name
        self.default_model = default_model
        self.cost_per_token: float = 0.0
        self.latency_ms: float = 0.0

    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], **kwargs: Any) -> ModelResponse:
        """Invoke the provider with a chat-style messages array."""

    @abstractmethod
    def stream(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterable[ModelStreamChunk]:
        """Stream responses as an iterable of chunks."""

    # Backwards-compatibility wrappers
    def invoke(self, messages: List[Dict[str, str]], **kwargs: Any) -> ModelResponse:
        return self.generate(messages, **kwargs)

    def invoke_stream(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterable[ModelStreamChunk]:
        return self.stream(messages, **kwargs)

    def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[ToolSchema] | None = None,
        tool_choice: str = "auto",
        **kwargs: Any,
    ) -> ChatToolResponse:
        """
        Optional hook for providers that support model-driven tool calls.
        Default implementation falls back to a normal generate() call.
        """
        response = self.generate(messages, **kwargs)
        return ChatToolResponse(
            final_text=response.text,
            tool_calls=[],
            raw=response.raw,
            finish_reason=response.finish_reason,
        )


class DummyProvider(ModelProvider):
    """Deterministic provider used for tests/CI."""

    def __init__(self, name: str = "dummy", default_model: str | None = None) -> None:
        super().__init__(name, default_model=default_model or "dummy-model")

    def generate(self, messages: List[Dict[str, str]], **kwargs: Any) -> ModelResponse:
        user_content = messages[-1]["content"] if messages else ""
        return ModelResponse(
            provider=self.name,
            model=self.default_model or "dummy-model",
            messages=messages,
            text=f"[dummy output from {self.name}] {user_content}".strip(),
            raw={"messages": messages},
        )

    def stream(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterable[ModelStreamChunk]:
        # Simple one-chunk stream for deterministic behavior
        yield ModelStreamChunk(
            provider=self.name,
            model=self.default_model or "dummy-model",
            delta=f"[dummy output from {self.name}] {messages[-1]['content'] if messages else ''}".strip(),
            raw={"messages": messages},
            is_final=True,
        )
