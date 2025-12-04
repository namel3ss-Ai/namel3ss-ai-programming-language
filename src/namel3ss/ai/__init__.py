"""AI subsystem with model registry and providers."""

from .registry import ModelRegistry
from .providers import DummyProvider, ModelProvider
from .providers.anthropic import AnthropicProvider
from .providers.gemini import GeminiProvider
from .providers.generic_http import GenericHTTPProvider
from .providers.lmstudio import LMStudioProvider
from .providers.ollama import OllamaProvider
from .providers.openai import OpenAIProvider
from .providers.openai_compatible import OpenAICompatibleProvider
from .providers.http_json import HTTPJsonProvider

__all__ = [
    "ModelRegistry",
    "ModelProvider",
    "DummyProvider",
    "OpenAIProvider",
    "HTTPJsonProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "OllamaProvider",
    "LMStudioProvider",
    "GenericHTTPProvider",
    "OpenAICompatibleProvider",
]
