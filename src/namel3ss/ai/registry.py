"""
Model registry for Namel3ss AI runtime.
"""

from __future__ import annotations

from typing import Dict, Optional

from ..errors import Namel3ssError
from ..secrets.manager import SecretsManager
from .providers import DummyProvider, ModelProvider


class ModelRegistry:
    """Holds model definitions and provider instances."""

    def __init__(self, secrets: Optional[SecretsManager] = None) -> None:
        self.providers: Dict[str, ModelProvider] = {}
        self.models: Dict[str, str] = {}  # model name -> provider name
        self.secrets = secrets or SecretsManager()

    def register_provider(self, name: str, provider: ModelProvider) -> None:
        self.providers[name] = provider

    def ensure_provider(self, name: str, default_model: Optional[str] = None) -> ModelProvider:
        if name not in self.providers:
            self.providers[name] = self._create_provider(name, default_model)
        return self.providers[name]

    def _create_provider(self, name: str, default_model: Optional[str] = None) -> ModelProvider:
        prefix = name.split(":", 1)[0]
        # Lazy import to keep optional dependency boundary small.
        if prefix == "openai":
            from .openai_provider import OpenAIProvider

            api_key = self.secrets.get("N3_OPENAI_API_KEY")
            base_url = self.secrets.get("N3_OPENAI_BASE_URL")
            model_hint = default_model or (name.split(":", 1)[1] if ":" in name else None)
            if api_key:
                return OpenAIProvider(
                    name=name,
                    api_key=api_key,
                    base_url=base_url,
                    default_model=model_hint,
                )
            # fall back to deterministic dummy when no key
            return DummyProvider(name)
        return DummyProvider(name)

    def register_model(self, model_name: str, provider_name: Optional[str]) -> None:
        provider_id = provider_name or "dummy"
        default_model = provider_name.split(":", 1)[1] if provider_name and ":" in provider_name else None
        self.ensure_provider(provider_id, default_model=default_model)
        self.models[model_name] = provider_id

    def get_provider_for_model(self, model_name: str) -> ModelProvider:
        if model_name not in self.models:
            raise Namel3ssError(f"Unknown model '{model_name}'")
        provider_name = self.models[model_name]
        if provider_name not in self.providers:
            raise Namel3ssError(f"Unknown provider '{provider_name}' for model '{model_name}'")
        return self.providers[provider_name]

    def list_providers(self) -> Dict[str, ModelProvider]:
        return dict(self.providers)
