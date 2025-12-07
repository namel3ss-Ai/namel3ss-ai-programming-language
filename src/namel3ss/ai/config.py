"""
Global AI configuration models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
import os


@dataclass
class GlobalAIConfig:
    max_cost_per_request: Optional[float] = None
    preferred_providers: List[str] = field(default_factory=list)
    fallback_providers: List[str] = field(default_factory=list)
    max_parallel_requests: Optional[int] = None
    default_chat_model: Optional[str] = None
    default_embedding_model: Optional[str] = None


def default_global_ai_config() -> GlobalAIConfig:
    env = os.environ
    return GlobalAIConfig(
        max_cost_per_request=None,
        preferred_providers=["dummy"],
        fallback_providers=[],
        max_parallel_requests=1,
        default_chat_model=env.get("N3_DEFAULT_CHAT_MODEL") or env.get("DEFAULT_CHAT_MODEL"),
        default_embedding_model=env.get("N3_DEFAULT_EMBEDDING_MODEL") or env.get("DEFAULT_EMBEDDING_MODEL"),
    )
