"""
Model registry for Namel3ss AI runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Dict, Optional

from ..errors import Namel3ssError
from ..secrets.manager import SecretsManager
from .providers import DummyProvider, ModelProvider
from .providers.anthropic import AnthropicProvider
from .providers.gemini import GeminiProvider
from .providers.generic_http import GenericHTTPProvider
from .providers.http_json import HTTPJsonProvider
from .providers.azure_openai import AzureOpenAIProvider
from .providers.lmstudio import LMStudioProvider
from .providers.ollama import OllamaProvider
from .providers.openai import OpenAIProvider
from .providers.openai_compatible import OpenAICompatibleProvider


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
        provider_name = cfg.provider
        if provider_name == "openai":
            api_key = self.secrets.get("N3_OPENAI_API_KEY") or self.secrets.get("OPENAI_API_KEY") or ""
            base_url = cfg.base_url or self.secrets.get("N3_OPENAI_BASE_URL")
            if api_key:
                return OpenAIProvider(
                    name="openai",
                    api_key=api_key,
                    base_url=base_url,
                    default_model=cfg.model,
                )
            return DummyProvider("dummy-openai", default_model=cfg.model)
        if provider_name == "anthropic":
            api_key = self.secrets.get("N3_ANTHROPIC_API_KEY") or self.secrets.get("ANTHROPIC_API_KEY") or ""
            if not api_key:
                raise Namel3ssError("Anthropic provider requires N3_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY")
            return AnthropicProvider(
                name="anthropic",
                api_key=api_key,
                base_url=cfg.base_url or self.secrets.get("N3_ANTHROPIC_BASE_URL"),
                default_model=cfg.model,
            )
        if provider_name == "azure_openai":
            api_key = self.secrets.get("AZURE_OPENAI_API_KEY") or self.secrets.get("N3_AZURE_OPENAI_API_KEY") or ""
            if not api_key:
                raise Namel3ssError("Azure OpenAI provider requires AZURE_OPENAI_API_KEY or N3_AZURE_OPENAI_API_KEY")
            base_url = cfg.base_url or self.secrets.get("AZURE_OPENAI_BASE_URL") or self.secrets.get("N3_AZURE_OPENAI_BASE_URL")
            deployment = cfg.model or (cfg.options.get("deployment") if cfg.options else None) or cfg.name
            if not base_url or not deployment:
                raise Namel3ssError("Azure OpenAI provider requires base_url and deployment name")
            api_version = cfg.options.get("api_version") if cfg.options else None
            return AzureOpenAIProvider(
                name="azure_openai",
                api_key=api_key,
                base_url=base_url,
                deployment=deployment,
                api_version=api_version or "2024-06-01",
                default_model=deployment,
            )
        if provider_name == "gemini":
            api_key = self.secrets.get("N3_GEMINI_API_KEY") or self.secrets.get("GEMINI_API_KEY") or ""
            if not api_key:
                raise Namel3ssError("Gemini provider requires N3_GEMINI_API_KEY or GEMINI_API_KEY")
            base = cfg.base_url or self.secrets.get("N3_GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com"
            version = (cfg.options.get("api_version") if cfg.options else None) or "v1beta"
            base_url = base if base.rstrip("/").endswith(version) else base.rstrip("/") + "/" + version
            return GeminiProvider(
                name="gemini",
                api_key=api_key,
                base_url=base_url,
                default_model=cfg.model,
            )
        if provider_name == "ollama":
            base_url = cfg.base_url or self.secrets.get("N3_OLLAMA_URL") or "http://localhost:11434"
            return OllamaProvider(name="ollama", base_url=base_url, default_model=cfg.model)
        if provider_name == "lmstudio":
            base_url = cfg.base_url or self.secrets.get("N3_LMSTUDIO_URL")
            if not base_url:
                raise Namel3ssError("LMStudio provider requires base_url (N3_LMSTUDIO_URL)")
            return LMStudioProvider(base_url=base_url, default_model=cfg.model)
        if provider_name in {"http", "generic"}:
            base_url = cfg.base_url or self.secrets.get("N3_GENERIC_AI_URL")
            api_key = self.secrets.get("N3_GENERIC_AI_API_KEY")
            if not base_url:
                raise Namel3ssError(f"HTTP provider for model '{cfg.name}' requires base_url")
            return GenericHTTPProvider(base_url=base_url, api_key=api_key, default_model=cfg.model)
        if provider_name == "openai_compat":
            if not cfg.base_url:
                raise Namel3ssError("OpenAI-compatible provider requires base_url")
            return OpenAICompatibleProvider(
                name="http",
                base_url=cfg.base_url,
                api_key=cfg.options.get("api_key") if cfg.options else None,
                default_model=cfg.model,
            )
        if provider_name == "http_json":
            if not cfg.base_url:
                raise Namel3ssError(f"HTTP JSON provider for model '{cfg.name}' requires base_url")
            path = (cfg.options.get("path") if cfg.options else None) or "/api/chat"
            headers = None
            if cfg.options.get("headers") if cfg.options else None:
                raw_headers = cfg.options.get("headers")
                if isinstance(raw_headers, str):
                    try:
                        headers = json.loads(raw_headers)
                    except Exception:
                        headers = None
                elif isinstance(raw_headers, dict):
                    headers = raw_headers
            return HTTPJsonProvider(
                name="http_json",
                base_url=cfg.base_url,
                path=path,
                response_path=cfg.response_path or (cfg.options.get("response_path") if cfg.options else None),
                default_model=cfg.model,
                headers=headers,
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
