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
HttpStreamClient = Callable[[str, Dict[str, Any], Dict[str, str]], Iterable[Dict[str, Any]]]


class GeminiProvider(ModelProvider):
    """Google Gemini provider (non-streaming for now)."""

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
        self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta"
        self._http_client = http_client or self._default_http_client
        self._http_stream = http_stream or self._default_http_stream

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
        parsed_json = None
        if json_mode and text:
            try:
                parsed_json = json.loads(text)
            except json.JSONDecodeError as exc:
                raise Namel3ssError(f"Gemini returned invalid JSON: {exc}") from exc
        return ModelResponse(provider=self.name, model=model, messages=messages, text=text, raw=data, json=parsed_json)

    def stream(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> Iterable[ModelStreamChunk]:
        if not self.api_key:
            raise Namel3ssError("Gemini API key missing for provider")
        model = kwargs.get("model") or self.default_model
        if not model:
            raise Namel3ssError("Gemini model name is required")
        contents = [{"role": msg.get("role", "user"), "parts": [{"text": msg.get("content", "")}]} for msg in messages]
        body = {"contents": contents, "stream": True}
        if json_mode:
            body["generationConfig"] = {"responseMimeType": "application/json"}
        url = f"{self._build_url(model)}?key={urllib.parse.quote(self.api_key)}"
        chunks = self._http_stream(url, body, {"Content-Type": "application/json"})
        for raw_chunk in chunks:
            delta = ""
            finish_reason = None
            if isinstance(raw_chunk, dict):
                candidates = raw_chunk.get("candidates") or []
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        delta = parts[0].get("text", "") or ""
                    finish_reason = candidates[0].get("finish_reason")
            chunk_json = None
            if json_mode and delta:
                try:
                    chunk_json = json.loads(delta)
                except json.JSONDecodeError as exc:
                    raise Namel3ssError(f"Gemini returned invalid JSON: {exc}") from exc
            yield ModelStreamChunk(
                provider=self.name,
                model=model,
                delta=delta,
                raw=raw_chunk,
                json=chunk_json,
                finish_reason=finish_reason,
                is_final=finish_reason is not None,
            )

    def _default_http_client(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)

    def _default_http_stream(self, url: str, body: Dict[str, Any], headers: Dict[str, str]) -> Iterable[Dict[str, Any]]:
        # Basic fallback: reuse non-streaming client and wrap as a single chunk.
        yield self._default_http_client(url, body, headers)
