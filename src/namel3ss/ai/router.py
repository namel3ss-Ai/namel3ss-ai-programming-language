"""
Model router for selecting providers/models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import GlobalAIConfig, default_global_ai_config
from .registry import ModelRegistry


@dataclass
class SelectedModel:
    model_name: str
    provider_name: str


class ModelRouter:
    def __init__(self, registry: ModelRegistry, config: Optional[GlobalAIConfig] = None) -> None:
        self.registry = registry
        self.config = config or default_global_ai_config()

    def select_model(self, logical_name: Optional[str] = None) -> SelectedModel:
        # If logical name specified and known, return directly.
        if logical_name and logical_name in self.registry.model_configs:
            cfg = self.registry.model_configs[logical_name]
            return SelectedModel(model_name=cfg.name, provider_name=cfg.provider)

        # Try preferred providers first.
        for provider in self.config.preferred_providers:
            for cfg in self.registry.model_configs.values():
                if cfg.provider == provider:
                    return SelectedModel(model_name=cfg.name, provider_name=cfg.provider)

        # Fallback to any model deterministically.
        if self.registry.model_configs:
            model_name = sorted(self.registry.model_configs.keys())[0]
            cfg = self.registry.model_configs[model_name]
            return SelectedModel(model_name=cfg.name, provider_name=cfg.provider)

        # If nothing registered, raise.
        raise ValueError("No models available for routing")
