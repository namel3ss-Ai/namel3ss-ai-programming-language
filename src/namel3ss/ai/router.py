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
    def __init__(
        self, registry: ModelRegistry, config: Optional[GlobalAIConfig] = None
    ) -> None:
        self.registry = registry
        self.config = config or default_global_ai_config()

    def select_model(self, logical_name: Optional[str] = None) -> SelectedModel:
        # If logical name specified and known, return directly.
        if logical_name and logical_name in self.registry.models:
            return SelectedModel(
                model_name=logical_name, provider_name=self.registry.models[logical_name]
            )

        # Try preferred providers first.
        for provider in self.config.preferred_providers:
            for model_name, prov in self.registry.models.items():
                if prov == provider:
                    return SelectedModel(model_name=model_name, provider_name=prov)

        # Fallback to any model deterministically.
        if self.registry.models:
            model_name = sorted(self.registry.models.keys())[0]
            return SelectedModel(
                model_name=model_name, provider_name=self.registry.models[model_name]
            )

        # If nothing registered, raise.
        raise ValueError("No models available for routing")
