"""
Flow graph and state models for FlowEngine V3.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..ir import IRFlow
from ..runtime.expressions import VariableEnvironment


@dataclass
class FlowNode:
    id: str
    kind: str  # "ai" | "agent" | "tool" | "branch" | "join" | "subflow" | ...
    config: dict
    next_ids: list[str]
    error_boundary_id: Optional[str] = None


@dataclass
class FlowGraph:
    nodes: dict[str, FlowNode]
    entry_id: str


@dataclass
class FlowError:
    node_id: str
    error: str
    handled: bool


@dataclass
class FlowState:
    data: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    errors: list[FlowError] = field(default_factory=list)
    inputs: list = field(default_factory=list)
    logs: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    checkpoints: list = field(default_factory=list)
    variables: VariableEnvironment | None = None
    _baseline: Dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        # Track a snapshot so we can compute deterministic deltas when merging branches.
        self._baseline = dict(self.data)
        if self.variables is None:
            self.variables = VariableEnvironment()

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def copy(self) -> "FlowState":
        clone = FlowState(
            data=dict(self.data),
            context=dict(self.context),
            errors=list(self.errors),
            inputs=list(self.inputs),
            logs=list(self.logs),
            notes=list(self.notes),
            checkpoints=list(self.checkpoints),
            variables=self.variables.clone() if self.variables else None,
        )
        clone._baseline = dict(self.data)
        return clone

    def diff(self) -> Dict[str, Any]:
        delta: Dict[str, Any] = {}
        for key, value in self.data.items():
            if key not in self._baseline or self._baseline[key] != value:
                delta[key] = value
        return delta


@dataclass
class FlowRuntimeContext:
    program: Any
    model_registry: Any
    tool_registry: Any
    agent_runner: Any
    router: Any
    tracer: Any = None
    metrics: Any = None
    secrets: Any = None
    memory_engine: Any = None
    rag_engine: Any = None
    frames: Any = None
    execution_context: Any = None
    max_parallel_tasks: int = 4
    parallel_semaphore: asyncio.Semaphore | None = None
    step_results: list | None = None
    variables: VariableEnvironment | None = None


def flow_ir_to_graph(flow: IRFlow) -> FlowGraph:
    """
    Translate the existing sequential IRFlow into a FlowGraph representation.
    This keeps DSL/IR stable while enabling richer runtime semantics.
    """

    nodes: dict[str, FlowNode] = {}
    prev_id: str | None = None
    entry_id: str | None = None

    for step in flow.steps:
        node_id = step.name
        node = FlowNode(
            id=node_id,
            kind=step.kind,
            config={
                "target": step.target,
                "step_name": step.name,
                "branches": getattr(step, "conditional_branches", None),
                "message": getattr(step, "message", None),
                "statements": getattr(step, "statements", None),
                "reason": "unconditional" if step.kind == "goto_flow" else None,
            },
            next_ids=[],
        )
        nodes[node_id] = node
        if prev_id:
            nodes[prev_id].next_ids.append(node_id)
        prev_id = node_id
        if entry_id is None:
            entry_id = node_id

    if entry_id is None:
        # Empty flows are allowed; create a no-op node so engine can still run.
        entry_id = "__empty__"
        nodes[entry_id] = FlowNode(
            id=entry_id,
            kind="noop",
            config={"step_name": "__empty__"},
            next_ids=[],
        )

    return FlowGraph(nodes=nodes, entry_id=entry_id)
