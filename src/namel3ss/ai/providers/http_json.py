"""Generic HTTP JSON provider for custom/local HTTP chat endpoints."""

from __future__ import annotations

import json
import urllib.parse
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
        path: str | None = None,
        response_path: str | None = None,
        default_model: str | None = None,
        http_client: Optional[HttpClient] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(name, default_model=default_model)
        self.base_url = base_url
        self.path = path or ""
        self.response_path = response_path
        self._http_client = http_client or self._default_http_client
        self._headers = headers or {"Content-Type": "application/json"}

    def generate(self, messages: List[Dict[str, str]], **kwargs: Any) -> ModelResponse:
        model_name = kwargs.get("model") or self.default_model or "http-json"
        url = urllib.parse.urljoin(self.base_url.rstrip("/") + "/", self.path.lstrip("/"))
        body: Dict[str, Any] = {"model": model_name, "messages": messages}
        extra_params = {k: v for k, v in kwargs.items() if k not in {"model", "json_mode"} and v is not None}
        if extra_params:
            body["parameters"] = extra_params
        data = self._http_client(url, body, dict(self._headers))
        content = self._extract_content(data)
        return ModelResponse(
            provider=self.name,
            model=model_name,
            messages=messages,
            text=content,
            raw=data,
        )

    def stream(self, messages: List[Dict[str, str]], **kwargs: Any) -> Iterable[ModelStreamChunk]:
        yield ModelStreamChunk(
            provider=self.name,
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

    def _extract_content(self, data: Dict[str, Any]) -> Any:
        if self.response_path:
            return _traverse_path(data, self.response_path)
        if "content" in data:
            return data["content"]
        if "message" in data and isinstance(data["message"], dict) and "content" in data["message"]:
            return data["message"]["content"]
        raise Namel3ssError("HTTP JSON provider expected 'content' in response")
