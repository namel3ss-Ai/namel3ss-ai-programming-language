"""Model router for selecting providers/models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
import urllib.error

from ..errors import Namel3ssError, ProviderAuthError
from ..secrets.manager import SecretsManager
from .config import GlobalAIConfig, default_global_ai_config
from .models import ModelResponse, ModelStreamChunk
from .providers import DummyProvider, ModelProvider
from .providers.anthropic import AnthropicProvider
from .providers.gemini import GeminiProvider
from .providers.generic_http import GenericHTTPProvider
from .providers.lmstudio import LMStudioProvider
from .providers.ollama import OllamaProvider
from .providers.openai import OpenAIProvider
from .registry import ModelConfig, ModelRegistry


@dataclass
class SelectedModel:
    model_name: str
    provider_name: str
    actual_model: Optional[str] = None


class ModelRouter:
    def __init__(
        self,
        registry: ModelRegistry,
        config: Optional[GlobalAIConfig] = None,
        secrets: Optional[SecretsManager] = None,
    ) -> None:
        self.registry = registry
        self.config = config or default_global_ai_config()
        self.secrets = secrets or registry.secrets
        self._provider_cache: Dict[str, ModelProvider] = {}

    def select_model(self, logical_name: Optional[str] = None) -> SelectedModel:
        # If logical name specified and known, return directly.
        if logical_name and logical_name in self.registry.model_configs:
            cfg = self.registry.model_configs[logical_name]
            return SelectedModel(model_name=cfg.name, provider_name=cfg.provider, actual_model=cfg.model)

        # Try preferred providers first.
        for provider in self.config.preferred_providers:
            for cfg in self.registry.model_configs.values():
                if cfg.provider == provider:
                    return SelectedModel(model_name=cfg.name, provider_name=cfg.provider, actual_model=cfg.model)

        # Fallback to any model deterministically.
        if self.registry.model_configs:
            model_name = sorted(self.registry.model_configs.keys())[0]
            cfg = self.registry.model_configs[model_name]
            return SelectedModel(model_name=cfg.name, provider_name=cfg.provider, actual_model=cfg.model)

        # If nothing registered, raise.
        raise ValueError("No models available for routing")

    # Provider dispatch helpers
    def _provider_for_prefix(self, prefix: str, default_model: Optional[str]) -> ModelProvider:
        if prefix in self._provider_cache:
            return self._provider_cache[prefix]

        # Route through the registry's provider factory for consistent config handling.
        temp_cfg = ModelConfig(
            name=f"temp:{prefix}",
            provider=prefix,
            model=default_model,
        )
        provider = self.registry._create_provider(temp_cfg)

        self._provider_cache[prefix] = provider
        return provider

    def _ensure_registered_from_spec(self, model_spec: str) -> ModelConfig:
        if model_spec in self.registry.model_configs:
            return self.registry.model_configs[model_spec]
        if ":" in model_spec:
            prefix, model_name = model_spec.split(":", 1)
        else:
            prefix, model_name = model_spec, None
        self.registry.register_model(model_spec, f"{prefix}:{model_name}" if model_name else prefix)
        return self.registry.model_configs[model_spec]

    def _resolve(self, model: Optional[str]) -> Tuple[ModelProvider, str, SelectedModel]:
        target_model = model or self.config.default_chat_model
        if not target_model and self.registry.providers_config.default:
            default_name = self.registry.providers_config.default
            default_cfg = self.registry.providers_config.providers.get(default_name)
            if default_cfg and default_cfg.model_default:
                target_model = default_cfg.model_default
                model = target_model
        if target_model:
            cfg = self._ensure_registered_from_spec(target_model)
            provider = self.registry.get_provider_for_model(cfg.name)
            selection = SelectedModel(model_name=cfg.name, provider_name=cfg.provider, actual_model=cfg.model)
            return provider, cfg.model or cfg.name, selection
        selection = self.select_model(None)
        provider = self.registry.get_provider_for_model(selection.model_name)
        return provider, selection.actual_model or selection.model_name, selection

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        json_mode: bool = False,
        **kwargs: any,
    ) -> ModelResponse:
        provider, actual_model, selection = self._resolve(model)
        try:
            return provider.generate(messages=messages, model=actual_model, json_mode=json_mode, **kwargs)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderAuthError(
                    f"Provider '{selection.provider_name}' rejected the API key (unauthorized). Check your key and account permissions.",
                    code="N3P-1802",
                ) from exc
            raise
        except Exception as exc:
            # Fallbacks
            for fallback_prefix in self.config.fallback_providers:
                try:
                    fb_provider = self._provider_for_prefix(fallback_prefix, default_model=actual_model)
                    return fb_provider.generate(messages=messages, model=actual_model, json_mode=json_mode, **kwargs)
                except Exception:
                    continue
            raise Namel3ssError(f"Model routing failed for {selection.provider_name}: {exc}") from exc

    def stream(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        json_mode: bool = False,
        **kwargs: any,
    ) -> Iterable[ModelStreamChunk]:
        provider, actual_model, selection = self._resolve(model)
        try:
            return provider.stream(messages=messages, model=actual_model, json_mode=json_mode, **kwargs)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderAuthError(
                    f"Provider '{selection.provider_name}' rejected the API key (unauthorized). Check your key and account permissions.",
                    code="N3P-1802",
                ) from exc
            raise
        except Exception as exc:
            for fallback_prefix in self.config.fallback_providers:
                try:
                    fb_provider = self._provider_for_prefix(fallback_prefix, default_model=actual_model)
                    return fb_provider.stream(messages=messages, model=actual_model, json_mode=json_mode, **kwargs)
                except Exception:
                    continue
            raise Namel3ssError(f"Model routing failed for {selection.provider_name}: {exc}") from exc

    # Basic cost-aware auto selection using static costs
    def auto_select(self) -> SelectedModel:
        cost_order = [
            ("gemini", 0.0008),
            ("openai", 0.001),
            ("anthropic", 0.0012),
            ("ollama", 0.002),
            ("lmstudio", 0.0025),
            ("generic", 0.003),
            ("dummy", 999),
        ]
        available = []
        for provider, cost in cost_order:
            try:
                prov = self._provider_for_prefix(provider, default_model=None)
                available.append((provider, cost, prov))
            except Exception:
                continue
        if not available:
            raise Namel3ssError("No providers available for auto routing")
        provider_name, _cost, _prov = sorted(available, key=lambda x: x[1])[0]
        logical = f"{provider_name}:auto"
        self.registry.register_model(logical, logical)
        return SelectedModel(model_name=logical, provider_name=provider_name, actual_model="auto")
