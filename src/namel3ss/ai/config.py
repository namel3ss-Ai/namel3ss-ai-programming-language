"""
Global AI configuration models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GlobalAIConfig:
    max_cost_per_request: Optional[float] = None
    preferred_providers: List[str] = field(default_factory=list)
    fallback_providers: List[str] = field(default_factory=list)
    max_parallel_requests: Optional[int] = None


def default_global_ai_config() -> GlobalAIConfig:
    return GlobalAIConfig(
        max_cost_per_request=None,
        preferred_providers=["dummy"],
        fallback_providers=[],
        max_parallel_requests=1,
    )
