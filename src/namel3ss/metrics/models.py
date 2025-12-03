"""
Metrics models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostEvent:
    operation: str  # e.g., "ai_call", "tool_call", "agent_run", "flow_run"
    tokens_in: int
    tokens_out: int
    cost: float
    provider: str
