"""Shared data models for AI provider responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Optional[int]]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ModelResponse:
    provider: str
    model: str
    messages: Iterable[Dict[str, Any]]
    text: str
    raw: Any
    usage: Optional[TokenUsage] = None
    finish_reason: Optional[str] = None
    cost: Optional[float] = None
    json: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "messages": list(self.messages),
            "result": self.text,
            "raw": self.raw,
            "usage": self.usage.to_dict() if self.usage else None,
            "finish_reason": self.finish_reason,
            "cost": self.cost,
            "json": self.json,
        }

    # Backwards-compatibility helpers to behave dict-like where older code calls .get
    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:  # pragma: no cover - compatibility
        return self.to_dict()[key]


@dataclass(frozen=True)
class ModelStreamChunk:
    provider: str
    model: str
    delta: str
    raw: Any
    is_final: bool = False
    usage: Optional[TokenUsage] = None
    finish_reason: Optional[str] = None
    json: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "delta": self.delta,
            "raw": self.raw,
            "is_final": self.is_final,
            "usage": self.usage.to_dict() if self.usage else None,
            "finish_reason": self.finish_reason,
            "json": self.json,
        }
