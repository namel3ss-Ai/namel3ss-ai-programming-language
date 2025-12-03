"""
Agent planning and results models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

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

__all__ = [
    "AgentStep",
    "AgentStepEvaluation",
    "AgentExecutionPlan",
    "AgentStepResult",
    "AgentPlanResult",
    "AgentPlan",
    "AgentRunResult",
]
