from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from ...errors import Namel3ssError
from ...observability.metrics import default_metrics
from ...runtime.expressions import EvaluationError
from ..errors import ReturnSignal, TimedStepError
from ..graph import FlowNode, FlowRuntimeContext, FlowState
from ..models import FlowStepResult

__all__ = ["_execute_with_timing", "_extract_duration"]


async def _execute_with_timing(
    self, node: FlowNode, state: FlowState, runtime_ctx: FlowRuntimeContext
) -> Optional[FlowStepResult]:
    # Evaluate conditional guard (when) if present
    when_expr = node.config.get("when")
    if when_expr is not None:
        evaluator = self._build_evaluator(state, runtime_ctx)
        try:
            cond_val = evaluator.evaluate(when_expr)
        except EvaluationError as exc:  # pragma: no cover - flows expression errors already covered elsewhere
            raise Namel3ssError(str(exc))
        if not cond_val:
            # Optionally log skip
            if runtime_ctx.event_logger:
                try:
                    runtime_ctx.event_logger.log(
                        {
                            "kind": "flow",
                            "event_type": "step_skipped",
                            "flow_name": state.context.get("flow_name"),
                            "step": node.config.get("step_name", node.id),
                            "reason": "when evaluated to false",
                        }
                    )
                except Exception:
                    pass
            return None

    resolved_kind = self._resolve_step_kind(node)
    step_name = node.config.get("step_name", node.id)
    timeout = node.config.get("timeout_seconds")
    target_label = node.config.get("target") if isinstance(node.config, dict) else None
    target_label = target_label or node.id
    start = time.monotonic()
    if runtime_ctx.event_logger:
        try:
            runtime_ctx.event_logger.log(
                {
                    "kind": "step",
                    "event_type": "start",
                    "flow_name": state.context.get("flow_name"),
                    "step_name": step_name,
                    "status": "running",
                    "step_kind": resolved_kind,
                }
            )
        except Exception:
            pass

    async def run_inner():
        if node.config.get("simulate_duration"):
            await asyncio.sleep(float(node.config["simulate_duration"]))
        return await self._execute_node(node, state, runtime_ctx, resolved_kind=resolved_kind)

    try:
        if timeout:
            result = await asyncio.wait_for(run_inner(), timeout=timeout)
        else:
            result = await run_inner()
    except ReturnSignal as rs:
        duration = time.monotonic() - start
        output_val = self._coerce_return_value(getattr(rs, "value", None))
        state.set("last_output", output_val)
        step_result = FlowStepResult(
            step_name=step_name,
            kind=resolved_kind,
            target=target_label,
            success=True,
            output=output_val,
            node_id=node.id,
            duration_seconds=duration if duration > 0 else 1e-6,
            cost=self._extract_cost(output_val),
        )
        default_metrics.record_step(step_result.node_id or step_result.step_name, step_result.duration_seconds, step_result.cost)
        if runtime_ctx.event_logger:
            try:
                runtime_ctx.event_logger.log(
                    {
                        "kind": "step",
                        "event_type": "end",
                        "flow_name": state.context.get("flow_name"),
                        "step_name": step_name,
                        "status": "success",
                        "step_kind": resolved_kind,
                    }
                )
            except Exception:
                pass
        rs.step_result = step_result
        raise
    except Exception as exc:
        duration = time.monotonic() - start
        if runtime_ctx.event_logger:
            try:
                runtime_ctx.event_logger.log(
                    {
                        "kind": "step",
                        "event_type": "error",
                        "flow_name": state.context.get("flow_name"),
                        "step_name": step_name,
                        "status": "error",
                        "message": str(exc),
                        "step_kind": resolved_kind,
                    }
                )
            except Exception:
                pass
        timed = TimedStepError(exc, duration)
        if hasattr(exc, "diagnostics"):
            timed.diagnostics = getattr(exc, "diagnostics")
        raise timed from exc
    duration = time.monotonic() - start
    if result:
        result.duration_seconds = duration if duration > 0 else 1e-6
        result.cost = self._extract_cost(result.output)
        default_metrics.record_step(result.node_id or result.step_name, result.duration_seconds, result.cost)
    if runtime_ctx.event_logger:
        try:
            runtime_ctx.event_logger.log(
                {
                    "kind": "step",
                    "event_type": "end",
                    "flow_name": state.context.get("flow_name"),
                    "step_name": step_name,
                    "status": "success",
                    "step_kind": resolved_kind,
                }
            )
        except Exception:
            pass
    return result


def _extract_duration(exc: Exception) -> float:
    if isinstance(exc, TimedStepError):
        return exc.duration
    return 0.0
