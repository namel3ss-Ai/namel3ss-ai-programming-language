"""Generic HTTP JSON provider for custom endpoints with response_path traversal."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional

from ...errors import Namel3ssError
from ..models import ModelResponse, ModelStreamChunk
from . import ModelProvider

HttpClient = Callable[[str, Dict[str, Any], Dict[str, str]], Dict[str, Any]]


def _traverse_path(data: Dict[str, Any], path: str) -> Any:
    node: Any = data
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise Namel3ssError(f"Path '{path}' not found in response")
    return node


class HTTPJsonProvider(ModelProvider):
    def __init__(
        self,
        name: str,
        base_url: str,
        response_path: str,
        default_model: str | None = None,
        http_client: Optional[HttpClient] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(name, default_model=default_model)
        self.base_url = base_url
        self.response_path = response_path
        self._http_client = http_client or self._default_http_client
        self._headers = headers or {"Content-Type": "application/json"}

    def generate(self, messages: List[Dict[str, str]], **kwargs: Any) -> ModelResponse:
        body = {"messages": messages, "parameters": {}}
        body["parameters"].update({k: v for k, v in kwargs.items() if v is not None})
        data = self._http_client(self.base_url, body, dict(self._headers))
        content = _traverse_path(data, self.response_path)
        return ModelResponse(
            provider="http_json",
            model=kwargs.get("model") or self.default_model or "http-json",
            messages=messages,
            text=content,
            raw=data,
        )

    def stream(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterable[ModelStreamChunk]:
        yield ModelStreamChunk(
            provider="http_json",
            model=kwargs.get("model") or self.default_model or "http-json",
            delta=self.generate(messages, **kwargs).text,
            raw=None,
            is_final=True,
        )

    def _default_http_client(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)
