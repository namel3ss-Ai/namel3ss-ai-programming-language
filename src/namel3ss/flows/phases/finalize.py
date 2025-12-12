from __future__ import annotations

from typing import Any

from ...ir import IRFlow
from ..models import FlowRunResult
from ..state.context import ExecutionContext

__all__ = ["finalize"]


def finalize(engine: Any, plan: dict[str, Any], result: FlowRunResult | None) -> FlowRunResult:
    context: ExecutionContext = plan["context"]
    runtime_ctx = plan["runtime_ctx"]
    state = plan["state"]
    flow: IRFlow = plan["flow"]
    if result and result.state and getattr(result.state, "variables", None):
        context.variables = result.state.variables.values
        runtime_ctx.variables = result.state.variables
    elif state and getattr(state, "variables", None):
        context.variables = state.variables.values
        runtime_ctx.variables = state.variables
    return result or FlowRunResult(flow_name=flow.name)
