"""
Flow runtime models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

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


@dataclass
class FlowRunResult:
    flow_name: str
    steps: List[FlowStepResult] = field(default_factory=list)
    state: Optional[FlowState] = None
    errors: List[FlowError] = field(default_factory=list)
