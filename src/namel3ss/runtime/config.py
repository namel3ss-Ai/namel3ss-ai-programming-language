"""
Configuration models for the runtime.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelProviderConfig:
    """Placeholder configuration for a model provider."""

    name: str
    endpoint: Optional[str] = None
    api_key_env: Optional[str] = None
