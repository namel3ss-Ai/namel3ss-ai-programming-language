"""
Simple OpenAI provider integration (sync, minimal).
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, Optional

from ..errors import Namel3ssError
from .providers import ModelProvider


class OpenAIProvider(ModelProvider):
    """
    Minimal provider that calls OpenAI's chat completions endpoint.

    This stays lightweight (std lib HTTP) to avoid extra dependencies.
    Tests can inject a custom http_client to avoid network calls.
    """

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str | None = None,
        default_model: str | None = None,
        http_client: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(name)
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1/chat/completions"
        self.default_model = default_model
        self._http_client = http_client or self._default_http_client

    def invoke(self, prompt: str | None, **kwargs: Any) -> Dict[str, Any]:
        if not self.api_key:
            raise Namel3ssError("OpenAI API key missing for provider")
        model = kwargs.get("model") or self.default_model or kwargs.get("model_name")
        if not model:
            raise Namel3ssError("OpenAI model name is required")
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt or ""}],
            "temperature": float(kwargs.get("temperature", 0)),
        }
        try:
            data = self._http_client(self.base_url, body)
        except Exception as exc:  # pragma: no cover - network errors
            raise Namel3ssError(f"OpenAI provider error: {exc}") from exc

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            if isinstance(data, dict)
            else ""
        )
        return {
            "provider": self.name,
            "prompt": prompt,
            "result": content,
        }

    def _default_http_client(self, url: str, body: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)
