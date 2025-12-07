"""Embedding router for selecting providers."""

from __future__ import annotations

from typing import Dict, Optional, Sequence

from ..errors import Namel3ssError
from ..secrets.manager import SecretsManager
from .embeddings import EmbeddingBatchResult, EmbeddingProvider, DeterministicEmbeddingProvider
from .embeddings.http_generic import HTTPEmbeddingProvider
from .embeddings.openai import OpenAIEmbeddingProvider


class EmbeddingRouter:
    def __init__(self, secrets: Optional[SecretsManager] = None) -> None:
        self.secrets = secrets or SecretsManager()
        self._cache: Dict[str, EmbeddingProvider] = {}

    def _provider_from_prefix(self, prefix: str, model: Optional[str]) -> EmbeddingProvider:
        if prefix in self._cache:
            return self._cache[prefix]
        if prefix in {"deterministic", "local"}:
            provider: EmbeddingProvider = DeterministicEmbeddingProvider()
        elif prefix == "openai":
            api_key = self.secrets.get("N3_OPENAI_API_KEY") or self.secrets.get("OPENAI_API_KEY") or ""
            if not api_key:
                raise Namel3ssError("OpenAI embeddings require N3_OPENAI_API_KEY or OPENAI_API_KEY")
            provider = OpenAIEmbeddingProvider(
                api_key=api_key,
                base_url=self.secrets.get_embedding_base_url(),
                model=model or self.secrets.get_embedding_model(),
            )
        elif prefix in {"http", "generic"}:
            base_url = self.secrets.get_embedding_base_url() or self.secrets.get("N3_GENERIC_EMBEDDINGS_URL")
            response_path = self.secrets.get_embedding_response_path() or "data.embedding"
            if not base_url:
                raise Namel3ssError("HTTP embeddings require base_url (N3_EMBEDDINGS_BASE_URL)")
            provider = HTTPEmbeddingProvider(
                base_url=base_url,
                response_path=response_path,
                model=model or self.secrets.get_embedding_model(),
                headers={"Authorization": f"Bearer {self.secrets.get('N3_GENERIC_EMBEDDINGS_API_KEY') or ''}".strip()},
            )
        else:
            provider = DeterministicEmbeddingProvider()
        self._cache[prefix] = provider
        return provider

    def embed(self, texts: Sequence[str], model: str | None = None) -> EmbeddingBatchResult:
        if not texts:
            return EmbeddingBatchResult(vectors=[], dim=0, model_name=model or "unknown", raw=None)
        if model is None or model == "auto":
            chosen_provider = (self.secrets.get_embedding_provider_name() or "deterministic").split(":", 1)[0]
            provider = self._provider_from_prefix(
                chosen_provider,
                model,
            )
            chosen_model = self.secrets.get_embedding_model() or self.secrets.get("N3_DEFAULT_EMBEDDING_MODEL")
            return provider.embed(texts, model=chosen_model)
        if ":" in model:
            prefix, model_name = model.split(":", 1)
        else:
            prefix, model_name = model, None
        provider = self._provider_from_prefix(prefix, model_name)
        return provider.embed(texts, model=model_name)
