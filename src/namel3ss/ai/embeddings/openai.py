"""OpenAI embeddings provider."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, Optional, Sequence

from ...errors import Namel3ssError
from . import EmbeddingBatchResult, EmbeddingProvider

HttpClient = Callable[[str, Dict[str, Any], Dict[str, str]], Dict[str, Any]]


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        http_client: Optional[HttpClient] = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1/embeddings"
        self.model = model or "text-embedding-3-small"
        self._http_client = http_client or self._default_http_client
        self.name = "openai"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _body(self, input_data: Sequence[str], model_override: str | None) -> Dict[str, Any]:
        return {"model": model_override or self.model, "input": list(input_data)}

    def embed(self, texts: Sequence[str], *, model: str | None = None, **kwargs: Any) -> EmbeddingBatchResult:
        if not self.api_key:
            raise Namel3ssError("OpenAI API key missing for embeddings")
        body = self._body(texts, model)
        data = self._http_client(self.base_url, body, self._headers())
        if not isinstance(data, dict) or "data" not in data:
            raise Namel3ssError("Invalid OpenAI embeddings response")
        vectors = [entry.get("embedding", []) for entry in data.get("data", [])]
        if not vectors:
            raise Namel3ssError("OpenAI embeddings response missing vectors")
        dim = len(vectors[0])
        return EmbeddingBatchResult(vectors=vectors, dim=dim, model_name=body["model"], raw=data)

    def _default_http_client(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)
