from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Optional

from ...errors import Namel3ssError
from ...observability.tracing import default_tracer
from ..errors import ReturnSignal
from ..graph import FlowError, FlowGraph, FlowRuntimeContext, FlowState, flow_ir_to_graph
from ..models import FlowRunResult, FlowStepMetrics, FlowStepResult

__all__ = ["execute", "a_run_flow"]

async def a_run_flow(
    self,
    graph: FlowGraph,
    state: FlowState,
    runtime_ctx: FlowRuntimeContext,
    flow_name: str | None = None,
    step_results: list[FlowStepResult] | None = None,
) -> FlowRunResult:
    if step_results is None:
        step_results = []
    tracer = runtime_ctx.tracer
    runtime_ctx.step_results = step_results
    flow_start = time.monotonic()
    root_span = default_tracer.start_span(
        f"flow.{flow_name or graph.entry_id}", attributes={"flow": flow_name or graph.entry_id}
    )

    if runtime_ctx.metrics:
        runtime_ctx.metrics.record_flow_run(flow_name or graph.entry_id)

    async def run_node(
        node_id: str,
        current_state: FlowState,
        boundary_id: str | None = None,
        stop_at: str | None = None,
    ) -> FlowState:
        if stop_at and node_id == stop_at:
            return current_state

        node = graph.nodes[node_id]
        resolved_kind = self._resolve_step_kind(node)
        target_label = node.config.get("target") if isinstance(node.config, dict) else None
        target_label = target_label or node.id
        boundary_for_children = node.error_boundary_id or boundary_id

        try:
            step_result = await self._execute_with_timing(node, current_state, runtime_ctx)
            if step_result:
                step_results.append(step_result)
        except ReturnSignal as rs:
            if getattr(rs, "step_result", None):
                step_results.append(rs.step_result)
            current_state.set("last_output", getattr(rs, "value", None))
            raise
        except Exception as exc:  # pragma: no cover - errors handled below
            duration = self._extract_duration(exc)
            handled = boundary_for_children is not None
            flow_error = FlowError(node_id=node.id, error=str(exc), handled=handled)
            current_state.errors.append(flow_error)
            diags = list(getattr(exc, "diagnostics", []) or [])
            failure = FlowStepResult(
                step_name=node.config.get("step_name", node.id),
                kind=resolved_kind,
                target=target_label,
                success=False,
                error_message=str(exc),
                handled=handled,
                node_id=node.id,
                duration_seconds=duration,
                diagnostics=diags,
            )
            step_results.append(failure)
            if runtime_ctx.metrics:
                runtime_ctx.metrics.record_flow_error(flow_name or graph.entry_id)
            if tracer:
                tracer.record_flow_error(
                    node_id=node.id,
                    node_kind=resolved_kind,
                    handled=handled,
                    boundary_id=boundary_for_children,
                )
            if handled:
                # expose error object to handler
                err_info = {"message": str(exc), "step": node.id}
                if current_state.variables:
                    if current_state.variables.has("error"):
                        current_state.variables.assign("error", err_info)
                    else:
                        try:
                            current_state.variables.declare("error", err_info)
                        except Exception:
                            current_state.variables.values["error"] = err_info
                if runtime_ctx.event_logger:
                    try:
                        runtime_ctx.event_logger.log(
                            {
                                "kind": "flow",
                                "event_type": "error_handler_start",
                                "flow": runtime_ctx.execution_context.flow_name if runtime_ctx.execution_context else None,
                                "failed_step": node.config.get("step_name", node.id),
                            }
                        )
                    except Exception:
                        pass
                handler_state = await run_node(boundary_for_children, current_state, None, stop_at)
                if runtime_ctx.event_logger:
                    try:
                        runtime_ctx.event_logger.log(
                            {
                                "kind": "flow",
                                "event_type": "error_handler_end",
                                "flow": runtime_ctx.execution_context.flow_name if runtime_ctx.execution_context else None,
                                "status": "success",
                            }
                        )
                    except Exception:
                        pass
                return handler_state
            raise

        # Stop execution if a redirect has been requested.
        if current_state.context.get("__redirect_flow__"):
            return current_state
        if current_state.context.get("__awaiting_input__"):
            return current_state

        # Branch evaluation
        if resolved_kind == "branch":
            next_id = self._evaluate_branch(node, current_state, runtime_ctx)
            if next_id is None:
                return current_state
            return await run_node(next_id, current_state, boundary_for_children, stop_at)

        # No outgoing edges -> terminate path
        if not node.next_ids:
            return current_state

        # Single edge -> continue
        if len(node.next_ids) == 1:
            return await run_node(node.next_ids[0], current_state, boundary_for_children, stop_at)

        # Parallel fan-out
        join_id = node.config.get("join") or node.config.get("join_id")
        branch_states = await self._run_parallel(
            node.next_ids,
            current_state,
            boundary_for_children,
            stop_at=join_id,
            runtime_ctx=runtime_ctx,
            run_node=run_node,
        )
        merged_state = self._merge_branch_states(current_state, node.next_ids, branch_states)
        if join_id:
            return await run_node(join_id, merged_state, boundary_for_children, None)
        return merged_state

    return_value: Any = None
    try:
        final_state = await run_node(graph.entry_id, state, boundary_id=None, stop_at=None)
        return_value = state.get("last_output")
    except ReturnSignal as rs:
        return_value = getattr(rs, "value", state.get("last_output"))
        state.set("last_output", return_value)
        final_state = state
    except Exception as exc:  # pragma: no cover - bubbled errors
        final_state = state
        final_state.errors.append(FlowError(node_id="__root__", error=str(exc), handled=False))
    if return_value is not None:
        return_value = self._coerce_return_value(return_value)
        state.set("last_output", return_value)
    total_duration = time.monotonic() - flow_start
    total_duration = max(total_duration, sum(r.duration_seconds for r in step_results))
    step_metrics = {
        r.node_id or r.step_name: FlowStepMetrics(step_id=r.node_id or r.step_name, duration_seconds=r.duration_seconds, cost=r.cost)
        for r in step_results
    }
    total_cost = sum(r.cost for r in step_results)
    default_tracer.finish_span(root_span)
    redirect_to = final_state.context.get("__redirect_flow__")
    unhandled_errors = [err for err in final_state.errors if not err.handled]
    final_state.errors = unhandled_errors
    return FlowRunResult(
        flow_name=flow_name or graph.entry_id,
        steps=step_results,
        state=final_state,
        errors=unhandled_errors,
        result=return_value,
        step_metrics=step_metrics,
        total_cost=total_cost,
        total_duration_seconds=total_duration,
        redirect_to=redirect_to,
        inputs=list(getattr(final_state, "inputs", [])),
        logs=list(getattr(final_state, "logs", [])),
        notes=list(getattr(final_state, "notes", [])),
        checkpoints=list(getattr(final_state, "checkpoints", [])),
    )

async def execute(engine: Any, plan: dict[str, Any]) -> FlowRunResult | None:
    runtime_ctx: FlowRuntimeContext = plan["runtime_ctx"]
    state: FlowState = plan["state"]
    current_flow = plan["flow"]
    tracer = plan.get("tracer")
    step_results = plan.get("step_results") or []
    result: FlowRunResult | None = None

    while True:
        graph = flow_ir_to_graph(current_flow)
        if tracer:
            tracer.start_flow(current_flow.name)
            tracer.record_flow_graph_build(current_flow.name, graph)
        if runtime_ctx.event_logger:
            try:
                runtime_ctx.event_logger.log(
                    {
                        "kind": "flow",
                        "event_type": "start",
                        "flow_name": current_flow.name,
                        "status": "running",
                    }
                )
            except Exception:
                pass
        state.context["flow_name"] = current_flow.name
        state.context.pop("__redirect_flow__", None)
        result = await engine.a_run_flow(
            graph,
            state,
            runtime_ctx,
            flow_name=current_flow.name,
            step_results=step_results,
        )
        if tracer:
            tracer.end_flow()
        if runtime_ctx.event_logger:
            try:
                has_unhandled = bool(result and result.errors)
                runtime_ctx.event_logger.log(
                    {
                        "kind": "flow",
                        "event_type": "end",
                        "flow_name": current_flow.name,
                        "status": "error" if has_unhandled else "success",
                        "message": result.errors[0].error if result and result.errors else None,
                    }
                )
            except Exception:
                pass
        redirect_to = result.redirect_to
        if not redirect_to:
            break
        next_flow = runtime_ctx.program.flows.get(redirect_to)
        if not next_flow:
            raise Namel3ssError(f"Flow '{current_flow.name}' redirects to missing flow '{redirect_to}'")
        current_flow = next_flow
        state = result.state or state
        plan["flow"] = current_flow
        plan["state"] = state

    plan["state"] = state
    plan["result"] = result
    plan["runtime_ctx"] = runtime_ctx
    plan["step_results"] = step_results
    return result
