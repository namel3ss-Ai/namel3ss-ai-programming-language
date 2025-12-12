from __future__ import annotations

from typing import Any, Optional

from ...runtime.expressions import VariableEnvironment
from ..graph import FlowState
from ...ir import IRFlow
from ..models import FlowStepResult
from ..state.context import ExecutionContext

__all__ = ["prepare"]


def prepare(
    engine: Any,
    flow: IRFlow,
    context: ExecutionContext,
    initial_state: Optional[dict[str, Any]] = None,
    stream_callback: Any = None,
) -> dict[str, Any]:
    runtime_ctx = engine._build_runtime_context(context, stream_callback=stream_callback)
    runtime_ctx.step_aliases = engine._collect_step_aliases(flow.steps)
    env = VariableEnvironment(context.variables)
    runtime_ctx.variables = env
    state = FlowState(
        data=initial_state or {},
        context={
            "flow_name": flow.name,
            "request_id": context.request_id,
            "app": context.app_name,
            "user": getattr(runtime_ctx, "user_context", None),
        },
        variables=env,
    )
    tracer = context.tracer
    step_results: list[FlowStepResult] = []
    return {
        "flow": flow,
        "context": context,
        "runtime_ctx": runtime_ctx,
        "state": state,
        "tracer": tracer,
        "step_results": step_results,
    }
