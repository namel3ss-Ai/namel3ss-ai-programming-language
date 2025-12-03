"""
Flow runtime models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class FlowStepResult:
    step_name: str
    kind: str
    target: str
    success: bool
    output: Any | None = None
    error_message: Optional[str] = None


@dataclass
class FlowRunResult:
    flow_name: str
    steps: List[FlowStepResult] = field(default_factory=list)
