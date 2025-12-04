"""Ollama local provider."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional

from ...errors import Namel3ssError
from ..models import ModelResponse, ModelStreamChunk
from . import ModelProvider

HttpClient = Callable[[str, Dict[str, Any], Dict[str, str]], Dict[str, Any]]
HttpStreamClient = Callable[[str, Dict[str, Any], Dict[str, str]], Iterable[Dict[str, Any]]]


class OllamaProvider(ModelProvider):
    """Local Ollama HTTP provider."""

    def __init__(
        self,
        name: str,
        base_url: str,
        default_model: str | None = None,
        http_client: Optional[HttpClient] = None,
        http_stream: Optional[HttpStreamClient] = None,
    ) -> None:
        super().__init__(name, default_model=default_model)
        self.base_url = base_url.rstrip("/")
        self._http_client = http_client or self._default_http_client
        self._http_stream = http_stream or self._default_http_stream

    def _build_body(self, messages: List[Dict[str, str]], stream: bool, **kwargs: Any) -> Dict[str, Any]:
        model = kwargs.get("model") or self.default_model
        if not model:
            raise Namel3ssError("Ollama model name is required")
        return {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

    def generate(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> ModelResponse:
        body = self._build_body(messages, False, **kwargs)
        if json_mode:
            body.setdefault("format", "json")
        data = self._http_client(f"{self.base_url}/api/chat", body, {"Content-Type": "application/json"})
        text = ""
        if isinstance(data, dict):
            text = data.get("message", {}).get("content", data.get("response", "")) or ""
        return ModelResponse(
            provider=self.name,
            model=body["model"],
            messages=messages,
            text=text,
            raw=data,
        )

    def stream(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> Iterable[ModelStreamChunk]:
        body = self._build_body(messages, True, **kwargs)
        if json_mode:
            body.setdefault("format", "json")
        for chunk in self._http_stream(f"{self.base_url}/api/chat", body, {"Content-Type": "application/json"}):
            delta = ""
            if isinstance(chunk, dict):
                delta = chunk.get("message", {}).get("content", chunk.get("response", "")) or ""
            yield ModelStreamChunk(
                provider=self.name,
                model=body["model"],
                delta=delta,
                raw=chunk,
                is_final=bool(chunk.get("done")) if isinstance(chunk, dict) else False,
            )

    def _default_http_client(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)

    def _default_http_stream(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Iterable[Dict[str, Any]]:
        yield self._default_http_client(url, body, headers)
