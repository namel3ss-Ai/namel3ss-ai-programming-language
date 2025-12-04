"""Generic OpenAI-compatible HTTP provider."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from ...errors import Namel3ssError
from .openai import HttpClient, HttpStreamClient, OpenAIProvider


class OpenAICompatibleProvider(OpenAIProvider):
    """Provider that speaks the OpenAI chat-completions schema against a custom base URL."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str | None = None,
        default_model: str | None = None,
        http_client: Optional[HttpClient] = None,
        http_stream: Optional[HttpStreamClient] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        headers = extra_headers or {}
        # If api_key is provided, use Authorization header; otherwise rely on caller-provided headers
        if api_key:
            headers = {"Authorization": f"Bearer {api_key}", **headers}
        super().__init__(
            name=name,
            api_key=api_key or "",
            base_url=base_url,
            default_model=default_model,
            http_client=http_client,
            http_stream=http_stream,
            extra_headers=headers,
        )

    def generate(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any):
        if not self.base_url:
            raise Namel3ssError("OpenAI-compatible provider requires base_url")
        return super().generate(messages, json_mode=json_mode, **kwargs)

    def stream(self, messages: List[Dict[str, str]], json_mode: bool = False, **kwargs: Any) -> Iterable[Any]:
        if not self.base_url:
            raise Namel3ssError("OpenAI-compatible provider requires base_url")
        return super().stream(messages, json_mode=json_mode, **kwargs)
