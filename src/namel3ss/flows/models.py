"""
Flow runtime models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, TypedDict

from .graph import FlowError, FlowState


class StreamEvent(TypedDict, total=False):
    kind: Literal["chunk", "done", "error", "flow_done", "state_change"]
    flow: str
    step: str
    channel: Optional[str]
    role: Optional[str]
    label: Optional[str]
    mode: Optional[str]
    delta: Optional[str]
    full: Optional[str]
    error: Optional[str]
    code: Optional[str]
    success: Optional[bool]
    result: Optional[dict]
    path: Optional[str]
    old_value: Any
    new_value: Any


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
    diagnostics: list[dict] = field(default_factory=list)


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
    inputs: List[dict] = field(default_factory=list)
    logs: List[dict] = field(default_factory=list)
    notes: List[dict] = field(default_factory=list)
    checkpoints: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        from dataclasses import asdict

        def _state_to_dict(state: FlowState | None) -> dict | None:
            if state is None:
                return None
            return {
                "data": dict(state.data),
                "context": dict(state.context),
                "errors": [asdict(err) for err in state.errors],
                "variables": dict(state.variables.values) if state.variables else {},
                "inputs": list(state.inputs),
                "logs": list(state.logs),
                "notes": list(state.notes),
                "checkpoints": list(state.checkpoints),
            }

        return {
            "flow_name": self.flow_name,
            "steps": [asdict(step) for step in self.steps],
            "state": _state_to_dict(self.state),
            "errors": [asdict(err) for err in self.errors],
            "step_metrics": {k: asdict(v) for k, v in self.step_metrics.items()},
            "total_cost": self.total_cost,
            "total_duration_seconds": self.total_duration_seconds,
            "redirect_to": self.redirect_to,
            "inputs": list(self.inputs),
            "logs": list(self.logs),
            "notes": list(self.notes),
            "checkpoints": list(self.checkpoints),
        }
