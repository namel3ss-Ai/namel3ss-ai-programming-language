"""
Flow runtime models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .graph import FlowError, FlowState


@dataclass
class FlowStepResult:
    step_name: str
    kind: str
    target: str
    success: bool
    output: Any | None = None
    error_message: Optional[str] = None
    handled: bool = False
    node_id: Optional[str] = None
    duration_seconds: float = 0.0
    cost: float = 0.0
    redirect_to: Optional[str] = None


@dataclass
class FlowStepMetrics:
    step_id: str
    duration_seconds: float
    cost: float


@dataclass
class FlowRunResult:
    flow_name: str
    steps: List[FlowStepResult] = field(default_factory=list)
    state: Optional[FlowState] = None
    errors: List[FlowError] = field(default_factory=list)
    step_metrics: Dict[str, FlowStepMetrics] = field(default_factory=dict)
    total_cost: float = 0.0
    total_duration_seconds: float = 0.0
    redirect_to: Optional[str] = None
