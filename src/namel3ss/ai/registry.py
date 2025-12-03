"""
Model registry for Namel3ss AI runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from ..errors import Namel3ssError
from ..secrets.manager import SecretsManager
from .http_json_provider import HTTPJsonProvider
from .openai_provider import OpenAIProvider
from .providers import DummyProvider, ModelProvider


@dataclass
class ModelConfig:
    name: str
    provider: str
    model: str | None = None
    base_url: str | None = None
    response_path: str | None = None
    options: Dict[str, str] = field(default_factory=dict)


class ModelRegistry:
    """Holds model definitions and provider instances."""

    def __init__(self, secrets: Optional[SecretsManager] = None) -> None:
        self.providers: Dict[str, ModelProvider] = {}  # keyed by model name
        self.model_configs: Dict[str, ModelConfig] = {}
        self.secrets = secrets or SecretsManager()

    def register_model(self, model_name: str, provider_name: Optional[str]) -> None:
        cfg = self.secrets.get_model_config(model_name)
        provider = (cfg.get("provider") or (provider_name.split(":", 1)[0] if provider_name else None) or "dummy").lower()
        default_model = cfg.get("model") or (provider_name.split(":", 1)[1] if provider_name and ":" in provider_name else None)
        model_config = ModelConfig(
            name=model_name,
            provider=provider,
            model=default_model,
            base_url=cfg.get("base_url"),
            response_path=cfg.get("response_path"),
            options=cfg.get("options", {}),
        )
        self.model_configs[model_name] = model_config
        self.providers[model_name] = self._create_provider(model_config)

    def _create_provider(self, cfg: ModelConfig) -> ModelProvider:
        if cfg.provider == "openai":
            api_key = self.secrets.get("N3_OPENAI_API_KEY") or ""
            base_url = cfg.base_url or self.secrets.get("N3_OPENAI_BASE_URL")
            if api_key:
                return OpenAIProvider(
                    name="openai",
                    api_key=api_key,
                    base_url=base_url,
                    default_model=cfg.model,
                )
            return DummyProvider("dummy-openai", default_model=cfg.model)
        if cfg.provider == "http_json":
            if not cfg.base_url:
                raise Namel3ssError(f"HTTP JSON provider for model '{cfg.name}' requires base_url")
            if not cfg.response_path:
                raise Namel3ssError(f"HTTP JSON provider for model '{cfg.name}' requires response_path")
            return HTTPJsonProvider(
                name="http_json",
                base_url=cfg.base_url,
                response_path=cfg.response_path,
                default_model=cfg.model,
            )
        return DummyProvider(cfg.provider or "dummy", default_model=cfg.model)

    def get_provider_for_model(self, model_name: str) -> ModelProvider:
        if model_name not in self.providers:
            raise Namel3ssError(f"Unknown model '{model_name}'")
        return self.providers[model_name]

    def list_providers(self) -> Dict[str, ModelProvider]:
        return dict(self.providers)

    @property
    def models(self) -> Dict[str, str]:
        """Compatibility map of model name -> provider name."""
        return {name: cfg.provider for name, cfg in self.model_configs.items()}

    def get_model_config(self, model_name: str) -> ModelConfig:
        if model_name not in self.model_configs:
            raise Namel3ssError(f"Unknown model '{model_name}'")
        return self.model_configs[model_name]
