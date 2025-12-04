"""Gemini provider."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional

from ...errors import Namel3ssError
from ..models import ModelResponse, ModelStreamChunk
from . import ModelProvider

HttpClient = Callable[[str, Dict[str, Any], Dict[str, str]], Dict[str, Any]]


class GeminiProvider(ModelProvider):
    """Google Gemini provider (non-streaming for now)."""

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str | None = None,
        default_model: str | None = None,
        http_client: Optional[HttpClient] = None,
    ) -> None:
        super().__init__(name, default_model=default_model)
        self.api_key = api_key
        self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta"
        self._http_client = http_client or self._default_http_client

    def _build_url(self, model: str) -> str:
        return urllib.parse.urljoin(self.base_url + "/", f"models/{model}:generateContent")

    def generate(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> ModelResponse:
        if not self.api_key:
            raise Namel3ssError("Gemini API key missing for provider")
        model = kwargs.get("model") or self.default_model
        if not model:
            raise Namel3ssError("Gemini model name is required")
        contents = [{"role": msg.get("role", "user"), "parts": [{"text": msg.get("content", "")}]} for msg in messages]
        body = {"contents": contents}
        if json_mode:
            body["generationConfig"] = {"responseMimeType": "application/json"}
        url = f"{self._build_url(model)}?key={urllib.parse.quote(self.api_key)}"
        data = self._http_client(url, body, {"Content-Type": "application/json"})
        text = ""
        if isinstance(data, dict):
            candidates = data.get("candidates") or []
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    text = parts[0].get("text", "") or ""
        return ModelResponse(provider=self.name, model=model, messages=messages, text=text, raw=data)

    def stream(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> Iterable[ModelStreamChunk]:
        raise NotImplementedError("Feature belongs to a future phase")

    def _default_http_client(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)
