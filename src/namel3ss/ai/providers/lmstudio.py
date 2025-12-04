"""LM Studio provider (OpenAI-compatible)."""

from __future__ import annotations

from typing import Optional

from .openai_compatible import OpenAICompatibleProvider, HttpClient, HttpStreamClient


class LMStudioProvider(OpenAICompatibleProvider):
    """LM Studio exposes an OpenAI-compatible API; this thin wrapper sets the provider name."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        default_model: str | None = None,
        http_client: Optional[HttpClient] = None,
        http_stream: Optional[HttpStreamClient] = None,
    ) -> None:
        super().__init__(
            name="lmstudio",
            base_url=base_url,
            api_key=api_key,
            default_model=default_model,
            http_client=http_client,
            http_stream=http_stream,
        )
