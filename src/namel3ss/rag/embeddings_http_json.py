"""
HTTP JSON embeddings provider for custom/Ollama-style endpoints.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from ..errors import Namel3ssError
from .embeddings import EmbeddingProvider


HttpClient = Callable[[str, Dict[str, Any], Dict[str, str]], Dict[str, Any]]


def _traverse_path(data: Dict[str, Any], path: str) -> Any:
    node: Any = data
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise Namel3ssError(f"Path '{path}' not found in response")
    return node


class HTTPJsonEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        base_url: str,
        response_path: str,
        model: str | None = None,
        headers: Optional[Dict[str, str]] = None,
        http_client: Optional[HttpClient] = None,
    ) -> None:
        super().__init__("http_json", model=model)
        self.base_url = base_url
        self.response_path = response_path
        self._headers = headers or {"Content-Type": "application/json"}
        self._http_client = http_client or self._default_http_client

    def embed_text(self, text: str, **kwargs) -> List[float]:
        return self.embed_batch([text], **kwargs)[0]

    def embed_batch(self, texts: List[str], **kwargs) -> List[List[float]]:
        body = {"texts": texts, "parameters": {k: v for k, v in kwargs.items() if v is not None}}
        try:
            data = self._http_client(self.base_url, body, dict(self._headers))
        except Exception as exc:  # pragma: no cover
            raise Namel3ssError(f"HTTP JSON embeddings error: {exc}") from exc
        vectors = _traverse_path(data, self.response_path)
        if not isinstance(vectors, list):
            raise Namel3ssError("Embedding response must be a list")
        return vectors

    def _default_http_client(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)
