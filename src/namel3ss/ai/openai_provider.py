"""
OpenAI Chat Completions provider (messages-based).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional

from ..errors import Namel3ssError
from .providers import ModelProvider


HttpClient = Callable[[str, Dict[str, Any], Dict[str, str]], Dict[str, Any]]
HttpStreamClient = Callable[[str, Dict[str, Any], Dict[str, str]], Iterable[Dict[str, Any]]]


class OpenAIProvider(ModelProvider):
    """
    OpenAI Chat Completions provider supporting messages, parameters, and streaming.
    The http_client/http_stream parameters allow deterministic mocking in tests.
    """

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
        self.base_url = base_url or "https://api.openai.com/v1/chat/completions"
        self._http_client = http_client or self._default_http_client
        self._http_stream = http_stream or self._default_http_stream

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_body(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        model = kwargs.get("model") or self.default_model
        if not model:
            raise Namel3ssError("OpenAI model name is required")
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        # Optional parameters
        for key in ("temperature", "top_p", "max_tokens", "response_format", "seed"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]
        return body

    def invoke(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        if not self.api_key:
            raise Namel3ssError("OpenAI API key missing for provider")
        body = self._build_body(messages, **kwargs)
        try:
            data = self._http_client(self.base_url, body, self._build_headers())
        except Exception as exc:  # pragma: no cover - runtime errors
            raise Namel3ssError(f"OpenAI provider error: {exc}") from exc
        content = ""
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices:
                content = choices[0].get("message", {}).get("content", "") or ""
        return {
            "provider": "openai",
            "model": body["model"],
            "messages": messages,
            "result": content,
            "raw": data,
        }

    def invoke_stream(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterable[Dict[str, Any]]:
        if not self.api_key:
            raise Namel3ssError("OpenAI API key missing for provider")
        body = self._build_body(messages, **kwargs)
        body["stream"] = True
        for chunk in self._http_stream(self.base_url, body, self._build_headers()):
            delta = ""
            if isinstance(chunk, dict):
                choices = chunk.get("choices") or []
                if choices:
                    delta = choices[0].get("delta", {}).get("content", "") or ""
            yield {
                "provider": "openai",
                "model": body["model"],
                "messages": messages,
                "delta": delta,
                "raw": chunk,
            }

    # Default HTTP client implementations (stdlib)
    def _default_http_client(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)

    def _default_http_stream(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Iterable[Dict[str, Any]]:
        # For simplicity, reuse non-streaming client and wrap as a single chunk.
        yield self._default_http_client(url, body, headers)
