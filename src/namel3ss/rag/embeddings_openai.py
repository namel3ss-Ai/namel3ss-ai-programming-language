"""
OpenAI embeddings provider (mockable).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from ..errors import Namel3ssError
from .embeddings import EmbeddingProvider


HttpClient = Callable[[str, Dict[str, Any], Dict[str, str]], Dict[str, Any]]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        http_client: Optional[HttpClient] = None,
    ) -> None:
        super().__init__("openai", model=model or "text-embedding-3-small")
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1/embeddings"
        self._http_client = http_client or self._default_http_client

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _body(self, input_data: List[str]) -> Dict[str, Any]:
        return {"model": self.model, "input": input_data}

    def embed_text(self, text: str, **kwargs) -> List[float]:
        vectors = self.embed_batch([text], **kwargs)
        return vectors[0]

    def embed_batch(self, texts: List[str], **kwargs) -> List[List[float]]:
        if not self.api_key:
            raise Namel3ssError("OpenAI API key missing for embeddings")
        body = self._body(texts)
        try:
            data = self._http_client(self.base_url, body, self._headers())
        except Exception as exc:  # pragma: no cover
            raise Namel3ssError(f"OpenAI embeddings error: {exc}") from exc
        if not isinstance(data, dict) or "data" not in data:
            raise Namel3ssError("Invalid OpenAI embeddings response")
        vectors: List[List[float]] = []
        for entry in data.get("data", []):
            vectors.append(entry.get("embedding", []))
        return vectors

    def _default_http_client(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)
