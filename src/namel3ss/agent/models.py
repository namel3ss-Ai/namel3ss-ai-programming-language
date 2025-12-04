"""
Agent planning and results models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .reflection import ReflectionConfig

from .plan import (
    AgentExecutionPlan,
    AgentPlanResult,
    AgentStep,
    AgentStepEvaluation,
    AgentStepResult,
)


# Backward-compatible aliases
AgentPlan = AgentExecutionPlan
AgentRunResult = AgentPlanResult


@dataclass
class AgentConfig:
    """
    Runtime configuration for an agent runner.

    Reflection is opt-in via the embedded ReflectionConfig. When None, reflection
    remains disabled and the runner behaves as before.
    """

    reflection: Optional[ReflectionConfig] = None

__all__ = [
    "AgentStep",
    "AgentStepEvaluation",
    "AgentExecutionPlan",
    "AgentStepResult",
    "AgentPlanResult",
    "AgentPlan",
    "AgentRunResult",
    "ReflectionConfig",
    "AgentConfig",
]
