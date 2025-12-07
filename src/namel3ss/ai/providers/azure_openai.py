"""Azure OpenAI chat provider."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional

from ...errors import Namel3ssError
from ..models import ModelResponse, ModelStreamChunk, TokenUsage
from . import ModelProvider

HttpClient = Callable[[str, Dict[str, Any], Dict[str, str]], Dict[str, Any]]
HttpStreamClient = Callable[[str, Dict[str, Any], Dict[str, str]], Iterable[Dict[str, Any]]]


class AzureOpenAIProvider(ModelProvider):
    """
    Azure-hosted OpenAI compatible provider. Uses deployment + api_version instead of model name.
    """

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        deployment: str,
        api_version: str = "2024-06-01",
        default_model: str | None = None,
        http_client: Optional[HttpClient] = None,
        http_stream: Optional[HttpStreamClient] = None,
    ) -> None:
        super().__init__(name, default_model=default_model or deployment)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.deployment = deployment
        self.api_version = api_version
        self._http_client = http_client or self._default_http_client
        self._http_stream = http_stream or self._default_http_stream

    def _endpoint(self) -> str:
        path = f"/openai/deployments/{self.deployment}/chat/completions"
        return urllib.parse.urljoin(self.base_url + "/", path) + f"?api-version={self.api_version}"

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise Namel3ssError("Azure OpenAI API key missing for provider")
        return {"Content-Type": "application/json", "api-key": self.api_key}

    def _parse_usage(self, payload: Dict[str, Any]) -> TokenUsage | None:
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return None
        return TokenUsage(
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )

    def generate(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> ModelResponse:
        body: Dict[str, Any] = {"messages": messages}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        for key in ("temperature", "top_p", "max_tokens", "seed", "frequency_penalty", "presence_penalty"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]
        data = self._http_client(self._endpoint(), body, self._headers())
        content = ""
        finish_reason = None
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices:
                choice = choices[0]
                finish_reason = choice.get("finish_reason")
                content = choice.get("message", {}).get("content", "") or ""
        return ModelResponse(
            provider=self.name,
            model=self.deployment,
            messages=messages,
            text=content,
            raw=data,
            usage=self._parse_usage(data) if isinstance(data, dict) else None,
            finish_reason=finish_reason,
        )

    def stream(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> Iterable[ModelStreamChunk]:
        body: Dict[str, Any] = {"messages": messages, "stream": True}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        for key in ("temperature", "top_p", "max_tokens", "seed", "frequency_penalty", "presence_penalty"):
            if key in kwargs and kwargs[key] is not None:
                body[key] = kwargs[key]
        for chunk in self._http_stream(self._endpoint(), body, self._headers()):
            delta = ""
            finish_reason = None
            if isinstance(chunk, dict):
                choices = chunk.get("choices") or []
                if choices:
                    choice = choices[0]
                    delta = choice.get("delta", {}).get("content", "") or ""
                    finish_reason = choice.get("finish_reason")
            yield ModelStreamChunk(
                provider=self.name,
                model=self.deployment,
                delta=delta,
                raw=chunk,
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
        yield self._default_http_client(url, body, headers)
