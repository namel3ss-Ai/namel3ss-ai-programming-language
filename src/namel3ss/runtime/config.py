"""
Configuration models for the runtime.
"""

from dataclasses import dataclass
import os
from typing import Optional


@dataclass
class ModelProviderConfig:
    """Placeholder configuration for a model provider."""

    name: str
    endpoint: Optional[str] = None
    api_key_env: Optional[str] = None


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def get_max_parallel_tasks() -> int:
    """
    Resolve the maximum parallel flow tasks from the environment.
    """
    return _env_int("N3_MAX_PARALLEL_TASKS", 4)
