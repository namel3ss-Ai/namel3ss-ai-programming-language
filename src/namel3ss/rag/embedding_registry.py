"""
Embedding provider registry with env-driven defaults.
"""

from __future__ import annotations

from typing import Dict, Optional

from ..errors import Namel3ssError
from ..secrets.manager import SecretsManager
from ..ai.embedding_router import EmbeddingRouter
from .embeddings import EmbeddingProvider, RouterEmbeddingProvider
from .embeddings_deterministic import DeterministicEmbeddingProvider
from .embeddings_http_json import HTTPJsonEmbeddingProvider
from .embeddings_openai import OpenAIEmbeddingProvider


class EmbeddingProviderRegistry:
    def __init__(self, secrets: Optional[SecretsManager] = None) -> None:
        self.secrets = secrets or SecretsManager()
        self.providers: Dict[str, EmbeddingProvider] = {}
        self.router = EmbeddingRouter(self.secrets)
        self.default_provider: EmbeddingProvider = self._create_default()

    def _create_default(self) -> EmbeddingProvider:
        provider_name = (self.secrets.get_embedding_provider_name() or "deterministic").lower()
        if provider_name == "openai":
            api_key = self.secrets.get("OPENAI_API_KEY") or self.secrets.get("N3_OPENAI_API_KEY") or ""
            if not api_key:
                return DeterministicEmbeddingProvider()
            model = self.secrets.get_embedding_model() or "text-embedding-3-small"
            base_url = self.secrets.get_embedding_base_url()
            return OpenAIEmbeddingProvider(api_key=api_key, base_url=base_url, model=model)
        if provider_name == "http_json":
            base_url = self.secrets.get_embedding_base_url()
            response_path = self.secrets.get_embedding_response_path()
            if not base_url or not response_path:
                return DeterministicEmbeddingProvider()
            model = self.secrets.get_embedding_model()
            return HTTPJsonEmbeddingProvider(base_url=base_url, response_path=response_path, model=model)
        if provider_name in {"router", "auto"}:
            return RouterEmbeddingProvider(router=self.router, model=self.secrets.get_embedding_model())
        return DeterministicEmbeddingProvider()

    def get_default_provider(self) -> EmbeddingProvider:
        return self.default_provider

    def get_provider(self, name: str) -> EmbeddingProvider:
        if name == self.default_provider.name:
            return self.default_provider
        if name not in self.providers:
            raise Namel3ssError(f"Embedding provider '{name}' not registered")
        return self.providers[name]
