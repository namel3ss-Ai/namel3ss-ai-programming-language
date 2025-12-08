"""
Model registry for Namel3ss AI runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Dict, Optional

from ..config import ProviderConfig, ProvidersConfig, load_config
from ..errors import Namel3ssError
from ..errors import ProviderAuthError, ProviderConfigError
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

    last_status: Dict[str, str] = {}

    def __init__(self, secrets: Optional[SecretsManager] = None, providers_config: ProvidersConfig | None = None) -> None:
        self.providers: Dict[str, ModelProvider] = {}  # keyed by model name
        self.model_configs: Dict[str, ModelConfig] = {}
        self.secrets = secrets or SecretsManager()
        cfg = providers_config or load_config().providers_config
        self.providers_config: ProvidersConfig = cfg or ProvidersConfig()
        self._provider_cache: Dict[str, ModelProvider] = {}
        self.provider_status: Dict[str, str] = {}

    def register_model(self, model_name: str, provider_name: Optional[str]) -> None:
        cfg = self.secrets.get_model_config(model_name)
        provider_hint = provider_name
        if provider_hint is None:
            provider_hint = self.providers_config.default
        default_model = cfg.get("model") or (provider_hint.split(":", 1)[1] if provider_hint and ":" in provider_hint else None)
        provider_key = (provider_hint.split(":", 1)[0] if provider_hint else None) or ""
        if provider_hint and provider_hint in self.providers_config.providers:
            provider_key = provider_hint
        provider = provider_key or "dummy"
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

    def _resolve_api_key(self, provider_name: str, cfg: ProviderConfig) -> str | None:
        if cfg.api_key:
            return cfg.api_key
        if cfg.api_key_env:
            return self.secrets.get(cfg.api_key_env)
        if cfg.type == "openai":
            return self.secrets.get("N3_OPENAI_API_KEY") or self.secrets.get("OPENAI_API_KEY")
        if cfg.type == "gemini":
            return self.secrets.get("N3_GEMINI_API_KEY") or self.secrets.get("GEMINI_API_KEY")
        if cfg.type == "anthropic":
            return self.secrets.get("N3_ANTHROPIC_API_KEY") or self.secrets.get("ANTHROPIC_API_KEY")
        return None

    def _create_provider(self, cfg: ModelConfig) -> ModelProvider:
        provider_key = cfg.provider or self.providers_config.default or "dummy"
        if provider_key in self._provider_cache:
            return self._provider_cache[provider_key]
        provider_cfg = self.providers_config.providers.get(provider_key)
        provider_type = provider_cfg.type if provider_cfg else (provider_key or "dummy")
        if provider_cfg is None:
            provider_cfg = ProviderConfig(type=provider_type)
        resolved_key = self._resolve_api_key(provider_key, provider_cfg)
        default_model = cfg.model or (provider_cfg.model_default if provider_cfg else None)

        def _missing_key() -> ProviderConfigError:
            return ProviderConfigError(
                f"Provider '{provider_key}' requires an API key. Set {provider_cfg.api_key_env or 'the provider key'} in your environment or configure api_key in namel3ss.config.",
                code="N3P-1801",
            )

        def _set_status(status: str) -> None:
            self.provider_status[provider_key] = status
            ModelRegistry.last_status[provider_key] = status

        if provider_type == "openai":
            if not resolved_key:
                _set_status("missing_key")
                raise _missing_key()
            base_url = (cfg.base_url or (provider_cfg.base_url if provider_cfg else None) or self.secrets.get("N3_OPENAI_BASE_URL"))
            provider = OpenAIProvider(
                name=provider_key,
                api_key=resolved_key,
                base_url=base_url,
                default_model=default_model,
            )
            _set_status("ok")
        elif provider_type == "anthropic":
            if not resolved_key:
                _set_status("missing_key")
                raise _missing_key()
            provider = AnthropicProvider(
                name=provider_key,
                api_key=resolved_key,
                base_url=(cfg.base_url or (provider_cfg.base_url if provider_cfg else None) or self.secrets.get("N3_ANTHROPIC_BASE_URL")),
                default_model=default_model,
            )
            _set_status("ok")
        elif provider_type == "azure_openai":
            api_key = resolved_key or self.secrets.get("AZURE_OPENAI_API_KEY") or self.secrets.get("N3_AZURE_OPENAI_API_KEY") or ""
            if not api_key:
                _set_status("missing_key")
                raise ProviderConfigError(
                    "Azure OpenAI provider requires AZURE_OPENAI_API_KEY or N3_AZURE_OPENAI_API_KEY",
                    code="N3P-1801",
                )
            base_url = cfg.base_url or (provider_cfg.base_url if provider_cfg else None) or self.secrets.get("AZURE_OPENAI_BASE_URL") or self.secrets.get("N3_AZURE_OPENAI_BASE_URL")
            deployment = default_model or cfg.name
            api_version = cfg.options.get("api_version") if cfg.options else None
            provider = AzureOpenAIProvider(
                name=provider_key,
                api_key=api_key,
                base_url=base_url,
                deployment=deployment,
                api_version=api_version or "2024-06-01",
                default_model=deployment,
            )
            _set_status("ok")
        elif provider_type == "gemini":
            if not resolved_key:
                _set_status("missing_key")
                raise _missing_key()
            base = cfg.base_url or (provider_cfg.base_url if provider_cfg else None) or self.secrets.get("N3_GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com"
            version = (cfg.options.get("api_version") if cfg.options else None) or "v1beta"
            base_url = base if base.rstrip("/").endswith(version) else base.rstrip("/") + "/" + version
            provider = GeminiProvider(
                name=provider_key,
                api_key=resolved_key,
                base_url=base_url,
                default_model=default_model,
            )
            _set_status("ok")
        elif provider_type == "ollama":
            base_url = cfg.base_url or (provider_cfg.base_url if provider_cfg else None) or self.secrets.get("N3_OLLAMA_URL") or "http://localhost:11434"
            provider = OllamaProvider(name=provider_key, base_url=base_url, default_model=default_model)
            _set_status("ok")
        elif provider_type == "lmstudio":
            base_url = cfg.base_url or (provider_cfg.base_url if provider_cfg else None) or self.secrets.get("N3_LMSTUDIO_URL")
            if not base_url:
                raise Namel3ssError("LMStudio provider requires base_url (N3_LMSTUDIO_URL)")
            provider = LMStudioProvider(base_url=base_url, default_model=default_model)
            _set_status("ok")
        elif provider_type in {"http", "generic"}:
            base_url = cfg.base_url or (provider_cfg.base_url if provider_cfg else None) or self.secrets.get("N3_GENERIC_AI_URL")
            if not base_url:
                raise Namel3ssError(f"HTTP provider for model '{cfg.name}' requires base_url")
            api_key = resolved_key or self.secrets.get("N3_GENERIC_AI_API_KEY")
            provider = GenericHTTPProvider(base_url=base_url, api_key=api_key, default_model=default_model)
            _set_status("ok")
        elif provider_type == "openai_compat":
            if not cfg.base_url and not (provider_cfg.base_url if provider_cfg else None):
                raise Namel3ssError("OpenAI-compatible provider requires base_url")
            provider = OpenAICompatibleProvider(
                name="http",
                base_url=cfg.base_url or (provider_cfg.base_url if provider_cfg else None) or "",
                api_key=resolved_key or (cfg.options.get("api_key") if cfg.options else None),
                default_model=default_model,
            )
            _set_status("ok")
        elif provider_type == "http_json":
            base_url = cfg.base_url or (provider_cfg.base_url if provider_cfg else None)
            if not base_url:
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
            provider = HTTPJsonProvider(
                name="http_json",
                base_url=base_url,
                path=path,
                response_path=cfg.response_path or (cfg.options.get("response_path") if cfg.options else None),
                default_model=default_model,
                headers=headers,
            )
            _set_status("ok")
        else:
            provider = DummyProvider(provider_key or "dummy", default_model=default_model)
            _set_status("unknown")
        self._provider_cache[provider_key] = provider
        return provider

    def resolve_provider_for_ai(self, ai_call) -> tuple[ModelProvider, str, str]:
        provider_name = getattr(ai_call, "provider", None) or self.providers_config.default
        if not provider_name:
            raise ProviderConfigError(
                "No provider configured. Add a provider config or set 'provider is \"...\"' on the ai block.",
                code="N3P-1801",
            )
        provider_cfg = self.providers_config.providers.get(provider_name)
        target_model = getattr(ai_call, "model_name", None) or (provider_cfg.model_default if provider_cfg else None)
        temp_cfg = ModelConfig(
            name=f"ai:{getattr(ai_call, 'name', provider_name)}",
            provider=provider_name,
            model=target_model,
            base_url=provider_cfg.base_url if provider_cfg else None,
            response_path=None,
            options=provider_cfg.extra if provider_cfg else {},
        )
        provider = self._create_provider(temp_cfg)
        final_model = temp_cfg.model or target_model or (provider_cfg.model_default if provider_cfg else None)
        return provider, final_model or "", provider_name

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
