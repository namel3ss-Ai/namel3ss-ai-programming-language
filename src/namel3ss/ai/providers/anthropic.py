"""Anthropic Claude provider."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional

from ...errors import Namel3ssError
from ..models import ModelResponse, ModelStreamChunk, TokenUsage
from . import ModelProvider

HttpClient = Callable[[str, Dict[str, Any], Dict[str, str]], Dict[str, Any]]
HttpStreamClient = Callable[[str, Dict[str, Any], Dict[str, str]], Iterable[Dict[str, Any]]]


class AnthropicProvider(ModelProvider):
    """Claude provider for text/JSON generation with optional streaming."""

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str | None = None,
        default_model: str | None = None,
        http_client: Optional[HttpClient] = None,
        http_stream: Optional[HttpStreamClient] = None,
    ) -> None:
        super().__init__(name, default_model=default_model)
        self.api_key = api_key
        self.base_url = base_url or "https://api.anthropic.com/v1/messages"
        self._http_client = http_client or self._default_http_client
        self._http_stream = http_stream or self._default_http_stream

    def _build_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        converted: List[Dict[str, Any]] = []
        for msg in messages:
            converted.append(
                {
                    "role": msg.get("role", "user"),
                    "content": [{"type": "text", "text": msg.get("content", "")}],
                }
            )
        return converted

    def generate(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> ModelResponse:
        if not self.api_key:
            raise Namel3ssError("Anthropic API key missing for provider")
        model = kwargs.get("model") or self.default_model
        if not model:
            raise Namel3ssError("Anthropic model name is required")
        body: Dict[str, Any] = {
            "model": model,
            "messages": self._convert_messages(messages),
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        if json_mode:
            body["system"] = (kwargs.get("system") or "") + "\nReturn JSON."
        data = self._http_client(self.base_url, body, self._build_headers())
        text = ""
        if isinstance(data, dict):
            content = data.get("content") or []
            if content:
                text = content[0].get("text", "") or ""
        usage = None
        if isinstance(data, dict) and data.get("usage"):
            u = data["usage"]
            usage = TokenUsage(
                prompt_tokens=u.get("input_tokens"),
                completion_tokens=u.get("output_tokens"),
                total_tokens=u.get("input_tokens", 0) + u.get("output_tokens", 0),
            )
        return ModelResponse(
            provider=self.name,
            model=model,
            messages=messages,
            text=text,
            raw=data,
            usage=usage,
        )

    def stream(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> Iterable[ModelStreamChunk]:
        if not self.api_key:
            raise Namel3ssError("Anthropic API key missing for provider")
        model = kwargs.get("model") or self.default_model
        if not model:
            raise Namel3ssError("Anthropic model name is required")
        body: Dict[str, Any] = {
            "model": model,
            "messages": self._convert_messages(messages),
            "max_tokens": kwargs.get("max_tokens", 1024),
            "stream": True,
        }
        for chunk in self._http_stream(self.base_url, body, self._build_headers()):
            delta = ""
            if isinstance(chunk, dict):
                delta = chunk.get("delta", {}).get("text", "") or chunk.get("text", "") or ""
            yield ModelStreamChunk(
                provider=self.name,
                model=model,
                delta=delta,
                raw=chunk,
                is_final=False,
            )

    def _default_http_client(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)

    def _default_http_stream(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Iterable[Dict[str, Any]]:
        yield self._default_http_client(url, body, headers)
