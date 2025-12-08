"""
Flow graph and state models for FlowEngine V3.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from ..ir import IRFlow, IRFlowLoop, IRFlowStep
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
    memory_stores: Any = None
    rag_engine: Any = None
    frames: Any = None
    vectorstores: Any = None
    records: Any = None
    execution_context: Any = None
    auth_config: Any = None
    user_context: dict | None = None
    max_parallel_tasks: int = 4
    parallel_semaphore: asyncio.Semaphore | None = None
    step_results: list | None = None
    variables: VariableEnvironment | None = None
    event_logger: Any = None
    stream_callback: Callable[[Any], Any] | None = None


def flow_ir_to_graph(flow: IRFlow) -> FlowGraph:
    """
    Translate the existing sequential IRFlow into a FlowGraph representation.
    This keeps DSL/IR stable while enabling richer runtime semantics.
    """

    def _ir_step_to_config(step: IRFlowStep) -> dict:
        return {
            "target": step.target,
            "step_name": step.name,
            "branches": getattr(step, "conditional_branches", None),
            "message": getattr(step, "message", None),
            "params": getattr(step, "params", {}) or {},
            "statements": getattr(step, "statements", None),
            "when": getattr(step, "when_expr", None),
            "stream": {
                "streaming": getattr(step, "streaming", False),
                "stream_channel": getattr(step, "stream_channel", None),
                "stream_role": getattr(step, "stream_role", None),
                "stream_label": getattr(step, "stream_label", None),
                "stream_mode": getattr(step, "stream_mode", None),
            },
            "tools_mode": getattr(step, "tools_mode", None),
        }

    def _loop_to_dict(loop: "IRFlowLoop") -> dict:
        return {
            "id": loop.name,
            "name": loop.name,
            "kind": "for_each",
            "config": {
                "step_name": loop.name,
                "var_name": loop.var_name,
                "iterable_expr": loop.iterable,
                "body": [_ir_item_to_inline(child) for child in loop.body],
            },
        }

    def _ir_item_to_inline(item: IRFlowStep | "IRFlowLoop") -> dict:
        if hasattr(item, "var_name"):
            return _loop_to_dict(item)  # type: ignore[arg-type]
        cfg = _ir_step_to_config(item)  # type: ignore[arg-type]
        return {
            "id": getattr(item, "name", cfg.get("step_name")),
            "name": getattr(item, "name", cfg.get("step_name")),
            "kind": getattr(item, "kind", "function"),
            **cfg,
        }

    nodes: dict[str, FlowNode] = {}
    prev_id: str | None = None
    entry_id: str | None = None

    error_entry_id: str | None = None
    if getattr(flow, "error_steps", None):
        prev_error: str | None = None
        for step in flow.error_steps:
            node_id = f"error::{step.name}"
            cfg = _ir_step_to_config(step)
            node = FlowNode(
                id=node_id,
                kind=step.kind,
                config={**cfg, "reason": "error_handler"},
                next_ids=[],
            )
            nodes[node_id] = node
            if prev_error:
                nodes[prev_error].next_ids.append(node_id)
            prev_error = node_id
            if error_entry_id is None:
                error_entry_id = node_id

    def _add_node_from_item(item: IRFlowStep | IRFlowLoop) -> None:
        nonlocal prev_id, entry_id
        if isinstance(item, IRFlowLoop):
            node_id = item.name
            node = FlowNode(
                id=node_id,
                kind="for_each",
                config={
                    "step_name": item.name,
                    "var_name": item.var_name,
                    "iterable_expr": item.iterable,
                    "body": [_ir_item_to_inline(child) for child in item.body],
                },
                next_ids=[],
                error_boundary_id=error_entry_id,
            )
        else:
            node_id = item.name
            cfg = _ir_step_to_config(item)
            node = FlowNode(
                id=node_id,
                kind=item.kind,
                config={**cfg, "reason": "unconditional" if item.kind == "goto_flow" else None},
                next_ids=[],
                error_boundary_id=error_entry_id,
            )
        nodes[node_id] = node
        if prev_id:
            nodes[prev_id].next_ids.append(node_id)
        prev_id = node_id
        if entry_id is None:
            entry_id = node_id

    for item in flow.steps:
        _add_node_from_item(item)

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
