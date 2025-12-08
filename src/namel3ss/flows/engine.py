"""
Flow execution engine V3: graph-based runtime with branching, parallelism, and
error boundaries.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from .. import ast_nodes
from ..agent.engine import AgentRunner
from ..ai.registry import ModelRegistry
from ..ai.router import ModelRouter
from ..errors import Namel3ssError, ProviderAuthError, ProviderConfigError
from ..runtime.auth import hash_password, verify_password
from ..ir import (
    IRAction,
    IRAskUser,
    IRCheckpoint,
    IRFlow,
    IRForEach,
    IRForm,
    IRIf,
    IRLet,
    IRLog,
    IRMatch,
    IRMatchBranch,
    IRNote,
    IRProgram,
    IRRepeatUpTo,
    IRRetry,
    IRReturn,
    IRTryCatch,
    IRSet,
    IRStatement,
)
from ..metrics.tracker import MetricsTracker
from ..observability.metrics import default_metrics
from ..observability.tracing import default_tracer
from ..runtime.context import (
    ExecutionContext,
    build_memory_messages,
    execute_ai_call_with_registry,
    persist_memory_state,
    run_memory_pipelines,
)
from ..runtime.eventlog import EventLogger
from ..runtime.expressions import EvaluationError, ExpressionEvaluator, VariableEnvironment
from ..runtime.frames import FrameRegistry
from ..runtime.vectorstores import VectorStoreRegistry
from ..secrets.manager import SecretsManager
from ..tools.registry import ToolRegistry, ToolConfig
from ..memory.engine import MemoryEngine
from ..memory.models import MemorySpaceConfig, MemoryType
from .graph import (
    FlowError,
    FlowGraph,
    FlowNode,
    FlowRuntimeContext,
    FlowState,
    flow_ir_to_graph,
)
from .models import FlowRunResult, FlowStepMetrics, FlowStepResult, StreamEvent


class ReturnSignal(Exception):
    def __init__(self, value: Any = None) -> None:
        self.value = value


class FlowEngine:
    def __init__(
        self,
        program: IRProgram,
        model_registry: ModelRegistry,
        tool_registry: ToolRegistry,
        agent_runner: AgentRunner,
        router: ModelRouter,
        metrics: Optional[MetricsTracker] = None,
        secrets: Optional[SecretsManager] = None,
        max_parallel_tasks: int = 4,
        global_stream_callback: Any = None,
    ) -> None:
        self.program = program
        self.model_registry = model_registry
        self.tool_registry = tool_registry
        self.agent_runner = agent_runner
        self.router = router
        self.metrics = metrics
        self.secrets = secrets
        self.max_parallel_tasks = max_parallel_tasks
        self.global_stream_callback = global_stream_callback
        self.frame_registry = FrameRegistry(program.frames if program else {})
        self.vector_registry = VectorStoreRegistry(program, secrets=secrets) if program else None
        # Register program-defined tools into the shared registry
        if program and getattr(program, "tools", None):
            for tool in program.tools.values():
                if tool.name not in self.tool_registry.tools:
                    self.tool_registry.register(
                        ToolConfig(
                            name=tool.name,
                            kind=tool.kind,
                            method=tool.method,
                            url_expr=getattr(tool, "url_expr", None),
                            url_template=getattr(tool, "url_template", None),
                            headers=getattr(tool, "headers", {}) or {},
                            query_params=getattr(tool, "query_params", {}) or {},
                            body_fields=getattr(tool, "body_fields", {}) or {},
                            body_template=getattr(tool, "body_template", None),
                            input_fields=list(getattr(tool, "input_fields", []) or []),
                        )
                    )

    def _build_runtime_context(self, context: ExecutionContext, stream_callback: Any = None) -> FlowRuntimeContext:
        mem_engine = context.memory_engine
        if mem_engine is None and self.program and self.program.memories:
            spaces = [
                MemorySpaceConfig(
                    name=mem.name,
                    type=MemoryType(mem.memory_type or MemoryType.CONVERSATION),
                    retention_policy=mem.retention,
                )
                for mem in self.program.memories.values()
            ]
            mem_engine = MemoryEngine(spaces=spaces)
        mem_stores = getattr(context, "memory_stores", None)
        user_context = getattr(context, "user_context", None) or {"id": None, "is_authenticated": False, "record": None}
        if getattr(context, "metadata", None) is not None and user_context.get("id") and "user_id" not in context.metadata:
            context.metadata["user_id"] = user_context.get("id")
        return FlowRuntimeContext(
            program=self.program,
            model_registry=self.model_registry,
            tool_registry=self.tool_registry,
            agent_runner=self.agent_runner,
            router=self.router,
            tracer=context.tracer,
            metrics=context.metrics or self.metrics,
            secrets=context.secrets or self.secrets,
            memory_engine=mem_engine,
            memory_stores=mem_stores,
            rag_engine=context.rag_engine,
            frames=self.frame_registry,
            vectorstores=self.vector_registry,
            records=getattr(self.program, "records", {}) if self.program else {},
            auth_config=getattr(self.program, "auth", None) if self.program else None,
            user_context=user_context,
            execution_context=context,
            max_parallel_tasks=self.max_parallel_tasks,
            parallel_semaphore=asyncio.Semaphore(self.max_parallel_tasks),
            variables=None,
            event_logger=EventLogger(
                self.frame_registry,
                session_id=context.metadata.get("session_id") if context.metadata else context.request_id,
            ),
            stream_callback=stream_callback or self.global_stream_callback,
        )

    def run_flow(
        self, flow: IRFlow, context: ExecutionContext, initial_state: Optional[dict[str, Any]] = None
    ) -> FlowRunResult:
        return asyncio.run(self.run_flow_async(flow, context, initial_state=initial_state))

    async def run_flow_async(
        self,
        flow: IRFlow,
        context: ExecutionContext,
        initial_state: Optional[dict[str, Any]] = None,
        stream_callback: Any = None,
    ) -> FlowRunResult:
        runtime_ctx = self._build_runtime_context(context, stream_callback=stream_callback)
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
        current_flow = flow
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
            result = await self.a_run_flow(
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

        if result and result.state and getattr(result.state, "variables", None):
            context.variables = result.state.variables.values
            runtime_ctx.variables = result.state.variables
        elif state and getattr(state, "variables", None):
            context.variables = state.variables.values
            runtime_ctx.variables = state.variables
        return result or FlowRunResult(flow_name=flow.name)

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
            boundary_for_children = node.error_boundary_id or boundary_id

            try:
                step_result = await self._execute_with_timing(node, current_state, runtime_ctx)
                if step_result:
                    step_results.append(step_result)
            except Exception as exc:  # pragma: no cover - errors handled below
                duration = self._extract_duration(exc)
                handled = boundary_for_children is not None
                flow_error = FlowError(node_id=node.id, error=str(exc), handled=handled)
                current_state.errors.append(flow_error)
                diags = list(getattr(exc, "diagnostics", []) or [])
                failure = FlowStepResult(
                    step_name=node.config.get("step_name", node.id),
                    kind=node.kind,
                    target=node.config.get("target", node.id),
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
                        node_kind=node.kind,
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
            if node.kind == "branch":
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

        try:
            final_state = await run_node(graph.entry_id, state, boundary_id=None, stop_at=None)
        except Exception as exc:  # pragma: no cover - bubbled errors
            final_state = state
            final_state.errors.append(FlowError(node_id="__root__", error=str(exc), handled=False))
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
            step_metrics=step_metrics,
            total_cost=total_cost,
            total_duration_seconds=total_duration,
            redirect_to=redirect_to,
            inputs=list(getattr(final_state, "inputs", [])),
            logs=list(getattr(final_state, "logs", [])),
            notes=list(getattr(final_state, "notes", [])),
            checkpoints=list(getattr(final_state, "checkpoints", [])),
        )

    async def _run_branch_with_limit(
        self,
        run_node: Callable[[str, FlowState, Optional[str], Optional[str]], asyncio.Future],
        node_id: str,
        branch_state: FlowState,
        boundary_id: str | None,
        stop_at: str | None,
        runtime_ctx: FlowRuntimeContext,
    ) -> FlowState:
        sem = runtime_ctx.parallel_semaphore
        if sem:
            async with sem:
                return await run_node(node_id, branch_state, boundary_id, stop_at)
        return await run_node(node_id, branch_state, boundary_id, stop_at)

    async def _run_parallel(
        self,
        next_ids: list[str],
        base_state: FlowState,
        boundary_id: str | None,
        stop_at: str | None,
        runtime_ctx: FlowRuntimeContext,
        run_node: Callable[[str, FlowState, Optional[str], Optional[str]], asyncio.Future],
    ) -> list[FlowState]:
        tracer = runtime_ctx.tracer
        if tracer:
            tracer.record_parallel_start(next_ids)
        tasks = []
        for nid in next_ids:
            branch_state = base_state.copy()
            tasks.append(
                asyncio.create_task(
                    self._run_branch_with_limit(
                        run_node, nid, branch_state, boundary_id, stop_at, runtime_ctx
                    )
                )
            )
        results = await asyncio.gather(*tasks)
        if tracer:
            tracer.record_parallel_join(next_ids)
        if runtime_ctx.metrics:
            runtime_ctx.metrics.record_parallel_branch(len(next_ids))
        return results

    def _merge_branch_states(
        self, target: FlowState, branch_ids: list[str], branch_states: list[FlowState]
    ) -> FlowState:
        for nid, branch_state in sorted(zip(branch_ids, branch_states), key=lambda pair: pair[0]):
            for key, value in branch_state.diff().items():
                namespaced = key
                # If the key is not already namespaced, prefix with branch id for clarity.
                if not key.startswith("step."):
                    namespaced = f"{nid}.{key}"
                target.data[namespaced] = value
            for err in branch_state.errors:
                target.errors.append(err)
            if target.variables and branch_state.variables:
                for name, value in branch_state.variables.values.items():
                    if target.variables.has(name):
                        target.variables.assign(name, value)
                    else:
                        target.variables.declare(name, value)
        return target

    def _evaluate_branch(self, node: FlowNode, state: FlowState, runtime_ctx: FlowRuntimeContext) -> str | None:
        condition = node.config.get("condition")
        branches = node.config.get("branches") or {}
        tracer = runtime_ctx.tracer
        result: Any = None

        if callable(condition):
            result = condition(state)
        elif isinstance(condition, str):
            # Restrict eval scope to state/context for safety.
            safe_globals = {"__builtins__": {}}
            safe_locals = {"state": state.data, "context": state.context}
            result = bool(eval(condition, safe_globals, safe_locals))  # noqa: S307
        else:
            result = bool(condition)

        if tracer:
            tracer.record_branch_eval(node.id, result)

        if isinstance(result, bool):
            key = "true" if result else "false"
            return branches.get(key) or branches.get(key.upper()) or branches.get(str(result)) or branches.get("default")
        if result is None:
            return branches.get("default")
        return branches.get(result) or branches.get(str(result)) or branches.get("default")

    async def _execute_node(
        self, node: FlowNode, state: FlowState, runtime_ctx: FlowRuntimeContext
    ) -> Optional[FlowStepResult]:
        tracer = runtime_ctx.tracer
        target = node.config.get("target", node.id)
        step_name = node.config.get("step_name", node.id)
        output: Any = None
        base_context = runtime_ctx.execution_context
        if base_context is None:
            base_context = ExecutionContext(
                app_name="__flow__",
                request_id=str(uuid4()),
                memory_engine=runtime_ctx.memory_engine,
                memory_stores=runtime_ctx.memory_stores,
                rag_engine=runtime_ctx.rag_engine,
                tracer=runtime_ctx.tracer,
                tool_registry=runtime_ctx.tool_registry,
                metrics=runtime_ctx.metrics,
                secrets=runtime_ctx.secrets,
            )

        params = node.config.get("params") or {}

        with default_tracer.span(
            f"flow.step.{node.kind}", attributes={"step": step_name, "flow_target": target, "kind": node.kind}
        ):
            if node.kind == "noop":
                output = node.config.get("output")
            elif node.kind == "ai":
                if target not in runtime_ctx.program.ai_calls:
                    raise Namel3ssError(f"Flow AI target '{target}' not found")
                ai_call = runtime_ctx.program.ai_calls[target]
                if runtime_ctx.event_logger:
                    try:
                        runtime_ctx.event_logger.log(
                            {
                                "kind": "ai",
                                "event_type": "start",
                                "flow_name": state.context.get("flow_name"),
                                "step_name": step_name,
                                "ai_name": ai_call.name,
                                "model": ai_call.model_name,
                                "status": "running",
                            }
                        )
                    except Exception:
                        pass
                stream_cfg = node.config.get("stream") or {}
                streaming = bool(stream_cfg.get("streaming")) or bool(params.get("streaming"))
                mode_val = stream_cfg.get("stream_mode") or params.get("stream_mode") or "tokens"
                if isinstance(mode_val, str):
                    mode_val = mode_val or "tokens"
                else:
                    mode_val = str(mode_val)
                if mode_val not in {"tokens", "sentences", "full"}:
                    mode_val = "tokens"
                stream_meta = {
                    "channel": stream_cfg.get("stream_channel") or params.get("stream_channel"),
                    "role": stream_cfg.get("stream_role") or params.get("stream_role"),
                    "label": stream_cfg.get("stream_label") or params.get("stream_label"),
                    "mode": mode_val,
                }
                tools_mode = node.config.get("tools_mode")
                if streaming:
                    output = await self._stream_ai_step(
                        ai_call,
                        base_context,
                        runtime_ctx,
                        step_name=step_name,
                        flow_name=state.context.get("flow_name") or "",
                        stream_meta=stream_meta,
                        tools_mode=tools_mode,
                    )
                else:
                    output = execute_ai_call_with_registry(
                        ai_call, runtime_ctx.model_registry, runtime_ctx.router, base_context, tools_mode=tools_mode
                    )
                if runtime_ctx.event_logger:
                    try:
                        runtime_ctx.event_logger.log(
                            {
                                "kind": "ai",
                                "event_type": "end",
                                "flow_name": state.context.get("flow_name"),
                                "step_name": step_name,
                                "ai_name": ai_call.name,
                                "model": ai_call.model_name,
                                "status": "success",
                            }
                        )
                    except Exception:
                        pass
            elif node.kind == "agent":
                raw_output = runtime_ctx.agent_runner.run(target, base_context)
                output = asdict(raw_output) if is_dataclass(raw_output) else raw_output
            elif node.kind == "tool":
                output = await self._execute_tool_call(node, state, runtime_ctx)
            elif node.kind in {"frame_insert", "frame_query", "frame_update", "frame_delete"}:
                params = node.config.get("params") or {}
                frame_name = params.get("frame") or target
                if not frame_name:
                    raise Namel3ssError(
                        "N3L-831: frame_insert/frame_query/frame_update/frame_delete requires a frame name."
                    )
                evaluator = self._build_evaluator(state, runtime_ctx)
                operation = node.kind.replace("frame_", "")
                if runtime_ctx.event_logger:
                    try:
                        runtime_ctx.event_logger.log(
                            {
                                "kind": "frame",
                                "event_type": "start",
                                "operation": operation,
                                "frame_name": frame_name,
                                "flow_name": state.context.get("flow_name"),
                                "step_name": step_name,
                                "status": "running",
                            }
                        )
                    except Exception:
                        pass
                if node.kind == "frame_insert":
                    values_expr = params.get("values") or {}
                    if not isinstance(values_expr, dict) or not values_expr:
                        raise Namel3ssError("N3L-832: frame_insert requires non-empty values.")
                    row: dict[str, Any] = {}
                    for k, v in values_expr.items():
                        row[k] = evaluator.evaluate(v) if isinstance(v, ast_nodes.Expr) else v
                    runtime_ctx.frames.insert(frame_name, row)
                    output = row
                elif node.kind == "frame_query":
                    filters_expr = params.get("where") or {}
                    filters: dict[str, Any] = {}
                    if isinstance(filters_expr, dict):
                        for k, v in filters_expr.items():
                            filters[k] = evaluator.evaluate(v) if isinstance(v, ast_nodes.Expr) else v
                    output = runtime_ctx.frames.query(frame_name, filters)
                elif node.kind == "frame_update":
                    set_expr = params.get("set") or {}
                    if not isinstance(set_expr, dict) or not set_expr:
                        raise Namel3ssError("N3L-840: frame_update step must define a non-empty 'set' block.")
                    filters_expr = params.get("where") or {}
                    filters: dict[str, Any] = {}
                    if isinstance(filters_expr, dict):
                        for k, v in filters_expr.items():
                            filters[k] = evaluator.evaluate(v) if isinstance(v, ast_nodes.Expr) else v
                    updates: dict[str, Any] = {}
                    for k, v in set_expr.items():
                        updates[k] = evaluator.evaluate(v) if isinstance(v, ast_nodes.Expr) else v
                    output = runtime_ctx.frames.update(frame_name, filters, updates)
                else:  # frame_delete
                    filters_expr = params.get("where") or {}
                    if not filters_expr:
                        raise Namel3ssError("N3L-841: frame_delete step requires a 'where' block to avoid deleting all rows.")
                    filters: dict[str, Any] = {}
                    if isinstance(filters_expr, dict):
                        for k, v in filters_expr.items():
                            filters[k] = evaluator.evaluate(v) if isinstance(v, ast_nodes.Expr) else v
                    output = runtime_ctx.frames.delete(frame_name, filters)
                if runtime_ctx.event_logger:
                    try:
                        payload = {
                            "kind": "frame",
                            "event_type": "end",
                            "operation": operation,
                            "frame_name": frame_name,
                            "flow_name": state.context.get("flow_name"),
                            "step_name": step_name,
                            "status": "success",
                        }
                        if node.kind in {"frame_query", "frame_update", "frame_delete"}:
                            payload["row_count"] = output if isinstance(output, (int, float)) else (len(output) if isinstance(output, list) else None)
                        runtime_ctx.event_logger.log(payload)
                    except Exception:
                        pass
            elif node.kind in {"db_create", "db_get", "db_update", "db_delete"}:
                params = node.config.get("params") or {}
                record_name = target
                if not record_name:
                    raise Namel3ssError(
                        f"N3L-1500: Step '{step_name}' must specify a record target."
                    )
                records = getattr(runtime_ctx, "records", {}) or getattr(runtime_ctx.program, "records", {})
                record = records.get(record_name)
                if not record:
                    raise Namel3ssError(
                        f"N3L-1500: Record '{record_name}' is not declared."
                    )
                evaluator = self._build_evaluator(state, runtime_ctx)
                output = self._execute_record_step(
                    kind=node.kind,
                    record=record,
                    params=params,
                    evaluator=evaluator,
                    runtime_ctx=runtime_ctx,
                    step_name=step_name,
                )
            elif node.kind in {"auth_register", "auth_login", "auth_logout"}:
                params = node.config.get("params") or {}
                auth_cfg = getattr(runtime_ctx, "auth_config", None)
                if not auth_cfg:
                    raise Namel3ssError("N3L-1600: Auth configuration is not declared.")
                records = getattr(runtime_ctx, "records", {}) or getattr(runtime_ctx.program, "records", {})
                record = records.get(getattr(auth_cfg, "user_record", None))
                if not record:
                    raise Namel3ssError("N3L-1600: Auth configuration references unknown user_record.")
                evaluator = self._build_evaluator(state, runtime_ctx)
                output = self._execute_auth_step(
                    kind=node.kind,
                    auth_config=auth_cfg,
                    record=record,
                    params=params,
                    evaluator=evaluator,
                    runtime_ctx=runtime_ctx,
                    step_name=step_name,
                    state=state,
                )
            elif node.kind == "vector_index_frame":
                params = node.config.get("params") or {}
                vector_store_name = params.get("vector_store") or target
                if not vector_store_name:
                    raise Namel3ssError("N3L-930: vector_index_frame step must specify a 'vector_store'.")
                if not runtime_ctx.vectorstores:
                    raise Namel3ssError("Vector store registry unavailable.")
                evaluator = self._build_evaluator(state, runtime_ctx)
                cfg = runtime_ctx.vectorstores.get(vector_store_name)
                filters_expr = params.get("where") or {}
                filters: dict[str, Any] = {}
                if isinstance(filters_expr, dict):
                    for k, v in filters_expr.items():
                        filters[k] = evaluator.evaluate(v) if isinstance(v, ast_nodes.Expr) else v
                if runtime_ctx.event_logger:
                    try:
                        runtime_ctx.event_logger.log(
                            {
                                "kind": "vector",
                                "event_type": "start",
                                "operation": "index_frame",
                                "vector_store": vector_store_name,
                                "frame": cfg.frame,
                                "flow_name": state.context.get("flow_name"),
                                "step_name": step_name,
                                "status": "running",
                            }
                        )
                    except Exception:
                        pass
                try:
                    rows = runtime_ctx.frames.query(cfg.frame, filters)
                    ids: list[str] = []
                    texts: list[str] = []
                    if isinstance(rows, list):
                        for row in rows:
                            if not isinstance(row, dict):
                                continue
                            id_val = row.get(cfg.id_column)
                            text_val = row.get(cfg.text_column)
                            if id_val is None or text_val is None:
                                continue
                            ids.append(str(id_val))
                            texts.append(str(text_val))
                    runtime_ctx.vectorstores.index_texts(vector_store_name, ids, texts)
                    output = len(ids)
                    if runtime_ctx.event_logger:
                        try:
                            runtime_ctx.event_logger.log(
                                {
                                    "kind": "vector",
                                    "event_type": "end",
                                    "operation": "index_frame",
                                    "vector_store": vector_store_name,
                                    "frame": cfg.frame,
                                    "flow_name": state.context.get("flow_name"),
                                    "step_name": step_name,
                                    "status": "success",
                                    "row_count": output,
                                }
                            )
                        except Exception:
                            pass
                except Exception as exc:
                    if runtime_ctx.event_logger:
                        try:
                            runtime_ctx.event_logger.log(
                                {
                                    "kind": "vector",
                                    "event_type": "error",
                                    "operation": "index_frame",
                                    "vector_store": vector_store_name,
                                    "frame": cfg.frame,
                                    "flow_name": state.context.get("flow_name"),
                                    "step_name": step_name,
                                    "status": "error",
                                    "message": str(exc),
                                }
                            )
                        except Exception:
                            pass
                    raise
            elif node.kind == "vector_query":
                params = node.config.get("params") or {}
                vector_store_name = params.get("vector_store") or target
                if not vector_store_name:
                    raise Namel3ssError("N3L-930: vector_index_frame step must specify a 'vector_store'.")
                if not runtime_ctx.vectorstores:
                    raise Namel3ssError("Vector store registry unavailable.")
                evaluator = self._build_evaluator(state, runtime_ctx)
                cfg = runtime_ctx.vectorstores.get(vector_store_name)
                query_expr = params.get("query_text")
                if query_expr is None:
                    raise Namel3ssError("N3L-941: vector_query step must define 'query_text'.")
                query_text = evaluator.evaluate(query_expr) if isinstance(query_expr, ast_nodes.Expr) else query_expr
                top_k_expr = params.get("top_k")
                top_k_val = 5
                if top_k_expr is not None:
                    top_k_val = evaluator.evaluate(top_k_expr) if isinstance(top_k_expr, ast_nodes.Expr) else top_k_expr
                try:
                    top_k_int = int(top_k_val)
                except Exception:
                    raise Namel3ssError("N3L-941: top_k must be an integer value.")
                if top_k_int < 1:
                    raise Namel3ssError("N3L-941: top_k must be at least 1.")
                if runtime_ctx.event_logger:
                    try:
                        runtime_ctx.event_logger.log(
                            {
                                "kind": "vector",
                                "event_type": "start",
                                "operation": "query",
                                "vector_store": vector_store_name,
                                "frame": cfg.frame,
                                "flow_name": state.context.get("flow_name"),
                                "step_name": step_name,
                                "status": "running",
                            }
                        )
                    except Exception:
                        pass
                try:
                    matches = runtime_ctx.vectorstores.query(vector_store_name, str(query_text), top_k_int, frames=runtime_ctx.frames)
                    # Build context string
                    context_parts: list[str] = []
                    enriched: list[dict] = []
                    for idx, m in enumerate(matches, start=1):
                        text_val = m.get("text")
                        enriched.append(m)
                        if text_val:
                            context_parts.append(f"Document {idx}:\n{text_val}")
                    context = "\n\n".join(context_parts)
                    output = {"matches": enriched, "context": context}
                    if runtime_ctx.event_logger:
                        try:
                            runtime_ctx.event_logger.log(
                                {
                                    "kind": "vector",
                                    "event_type": "end",
                                    "operation": "query",
                                    "vector_store": vector_store_name,
                                    "frame": cfg.frame,
                                    "flow_name": state.context.get("flow_name"),
                                    "step_name": step_name,
                                    "status": "success",
                                    "match_count": len(matches),
                                }
                            )
                        except Exception:
                            pass
                except Exception as exc:
                    if runtime_ctx.event_logger:
                        try:
                            runtime_ctx.event_logger.log(
                                {
                                    "kind": "vector",
                                    "event_type": "error",
                                    "operation": "query",
                                    "vector_store": vector_store_name,
                                    "frame": cfg.frame,
                                    "flow_name": state.context.get("flow_name"),
                                    "step_name": step_name,
                                    "status": "error",
                                    "message": str(exc),
                                }
                            )
                        except Exception:
                            pass
                    raise
            elif node.kind == "rag":
                if not runtime_ctx.rag_engine:
                    raise Namel3ssError("RAG engine unavailable for rag step")
                query = node.config.get("query") or state.get("last_output") or ""
                results = await runtime_ctx.rag_engine.a_retrieve(query, index_names=[target])
                output = [
                    {"text": r.item.text, "score": r.score, "source": r.source, "metadata": r.item.metadata}
                    for r in results
                ]
                if runtime_ctx.metrics:
                    runtime_ctx.metrics.record_rag_query(backends=[target])
            elif node.kind == "branch":
                output = {"branch": True}
            elif node.kind == "join":
                output = {"join": True}
            elif node.kind == "subflow":
                subflow = runtime_ctx.program.flows.get(target)
                if not subflow:
                    raise Namel3ssError(f"Subflow '{target}' not found")
                graph = flow_ir_to_graph(subflow)
                sub_state = state.copy()
                result = await self.a_run_flow(graph, sub_state, runtime_ctx, flow_name=target)
                output = {"subflow": target, "state": result.state.data if result.state else {}}
            elif node.kind == "script":
                statements = node.config.get("statements") or []
                output = await self._execute_script(statements, state, runtime_ctx, node.id)
            elif node.kind == "condition":
                output = await self._run_condition_node(node, state, runtime_ctx)
            elif node.kind == "function":
                func = node.config.get("callable")
                if not callable(func):
                    raise Namel3ssError(f"Function node '{node.id}' missing callable")
                output = func(state)
            elif node.kind == "parallel":
                output = await self._execute_parallel_block(node, state, runtime_ctx)
            elif node.kind == "for_each":
                output = await self._execute_for_each(node, state, runtime_ctx)
            elif node.kind == "try":
                output = await self._execute_try_catch(node, state, runtime_ctx)
            elif node.kind == "goto_flow":
                target_flow = node.config.get("target")
                reason = node.config.get("reason", "unconditional")
                if not target_flow:
                    raise Namel3ssError("'go to flow' requires a target flow name")
                state.context["__redirect_flow__"] = target_flow
                output = {"goto_flow": target_flow}
                if tracer:
                    tracer.record_flow_event(
                        "flow.goto",
                        {
                            "from_flow": state.context.get("flow_name"),
                            "to_flow": target_flow,
                            "step": node.config.get("step_name", node.id),
                            "reason": reason,
                        },
                    )
            else:
                raise Namel3ssError(f"Unsupported flow step kind '{node.kind}'")

        state.set(f"step.{node.id}.output", output)
        state.set("last_output", output)
        if tracer:
            tracer.record_flow_step(
                step_name=step_name,
                kind=node.kind,
                target=target,
                success=True,
                output_preview=str(output)[:200] if output is not None else None,
                node_id=node.id,
        )
        return FlowStepResult(
            step_name=step_name,
            kind=node.kind,
            target=target,
            success=True,
            output=output,
            node_id=node.id,
            redirect_to=state.context.get("__redirect_flow__"),
        )

    async def _stream_ai_step(
        self,
        ai_call,
        base_context: ExecutionContext,
        runtime_ctx: FlowRuntimeContext,
        step_name: str,
        flow_name: str,
        stream_meta: dict[str, object] | None = None,
        tools_mode: str | None = None,
    ):
        provider, provider_model, provider_name = runtime_ctx.model_registry.resolve_provider_for_ai(ai_call)
        provider_model = provider_model or ai_call.model_name
        messages: list[dict[str, str]] = []

        session_id = base_context.metadata.get("session_id") if base_context.metadata else None
        session_id = session_id or base_context.request_id or "default"
        metadata_user_id = base_context.metadata.get("user_id") if base_context.metadata else None
        user_id = str(metadata_user_id) if metadata_user_id is not None else None

        if getattr(ai_call, "system_prompt", None):
            messages.append({"role": "system", "content": ai_call.system_prompt or ""})

        memory_cfg = getattr(ai_call, "memory", None)
        memory_state: dict[str, Any] | None = None
        if memory_cfg and getattr(base_context, "memory_stores", None):
            memory_state, memory_messages = build_memory_messages(ai_call, base_context, session_id, user_id)
            messages.extend(memory_messages)
        elif getattr(ai_call, "memory_name", None) and base_context.memory_engine:
            try:
                history = base_context.memory_engine.load_conversation(ai_call.memory_name or "", session_id=session_id)
                messages.extend(history)
            except Exception:
                raise Namel3ssError(
                    f"Failed to load conversation history for memory '{ai_call.memory_name}'."
                )

        user_content = ai_call.input_source or (base_context.user_input or "")
        user_message = {"role": "user", "content": user_content}
        messages.append(user_message)

        if getattr(ai_call, "tools", None):
            requested_mode = (tools_mode or "auto").lower()
            if requested_mode != "none":
                raise Namel3ssError(
                    f"N3F-975: Streaming AI steps do not support tool calling (AI '{ai_call.name}'). "
                    "Disable streaming or set 'tools is \"none\"' on the step."
                )
        tools_payload = None

        full_text = ""
        mode = "tokens"
        channel = None
        role = None
        label = None
        if stream_meta:
            channel = stream_meta.get("channel")
            role = stream_meta.get("role")
            label = stream_meta.get("label")
            mode_candidate = stream_meta.get("mode") or mode
            if isinstance(mode_candidate, str):
                mode_candidate = mode_candidate or mode
            else:
                mode_candidate = str(mode_candidate)
            if mode_candidate in {"tokens", "sentences", "full"}:
                mode = mode_candidate
        sentence_buffer = ""

        async def emit(kind: str, **payload):
            event: StreamEvent = {
                "kind": kind,
                "flow": flow_name,
                "step": step_name,
                "channel": channel,
                "role": role,
                "label": label,
                "mode": mode,
            }
            event.update(payload)
            if runtime_ctx.stream_callback:
                await runtime_ctx.stream_callback(event)

        async def _flush_sentence_chunks(buffer: str, force: bool = False) -> str:
            remaining = buffer
            while True:
                boundary_idx = None
                for idx, ch in enumerate(remaining):
                    if ch in ".!?":
                        next_char = remaining[idx + 1] if idx + 1 < len(remaining) else ""
                        if not next_char or next_char.isspace():
                            boundary_idx = idx
                            break
                if boundary_idx is None:
                    break
                segment = remaining[: boundary_idx + 1]
                remaining = remaining[boundary_idx + 1 :]
                if segment.strip():
                    await emit("chunk", delta=segment)
                remaining = remaining.lstrip()
            if force and remaining.strip():
                await emit("chunk", delta=remaining)
                remaining = ""
            return remaining

        try:
            for chunk in provider.stream(messages=messages, model=provider_model, tools=tools_payload):
                delta = ""
                if isinstance(chunk, dict):
                    delta = chunk.get("delta") or ""
                else:
                    delta = getattr(chunk, "delta", "") or ""
                if delta:
                    delta_str = str(delta)
                    full_text += delta_str
                    if mode == "tokens":
                        await emit("chunk", delta=delta_str)
                    elif mode == "sentences":
                        sentence_buffer += delta_str
                        sentence_buffer = await _flush_sentence_chunks(sentence_buffer, force=False)
                    # mode == "full" defers emission until the end
            runtime_ctx.model_registry.provider_status[provider_name] = "ok"
            ModelRegistry.last_status[provider_name] = "ok"
            if mode == "sentences":
                sentence_buffer = await _flush_sentence_chunks(sentence_buffer, force=True)
            await emit("done", full=full_text)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                runtime_ctx.model_registry.provider_status[provider_name] = "unauthorized"
                ModelRegistry.last_status[provider_name] = "unauthorized"
                auth_err = ProviderAuthError(
                    f"Provider '{provider_name}' rejected the API key (unauthorized). Check your key and account permissions.",
                    code="N3P-1802",
                )
                await emit("error", error=str(auth_err), code=auth_err.code)
                raise auth_err
            await emit("error", error=str(exc), code=getattr(exc, "code", None))
            raise
        except ProviderConfigError as exc:
            await emit("error", error=str(exc), code=exc.code)
            raise
        except Exception as exc:
            await emit("error", error=str(exc), code=getattr(exc, "code", None))
            raise

        if memory_state:
            persist_memory_state(memory_state, ai_call, session_id, user_content, full_text, user_id)
            run_memory_pipelines(
                ai_call,
                memory_state,
                session_id,
                user_content,
                full_text,
                user_id,
                provider,
                provider_model,
            )
        elif getattr(ai_call, "memory_name", None) and base_context.memory_engine:
            try:
                base_context.memory_engine.append_conversation(
                    ai_call.memory_name or "",
                    messages=[
                        user_message,
                        {"role": "assistant", "content": full_text},
                    ],
                    session_id=session_id,
                )
            except Exception:
                pass
        return full_text

    async def _execute_parallel_block(self, node: FlowNode, state: FlowState, runtime_ctx: FlowRuntimeContext):
        children = node.config.get("steps") or node.config.get("children") or []
        fail_fast = bool(node.config.get("fail_fast", True))
        branch_ids = []
        tasks = []
        for idx, child in enumerate(children):
            child_id = child.get("id") or child.get("name") or f"{node.id}.child{idx}"
            branch_ids.append(child_id)
            child_state = state.copy()
            tasks.append(asyncio.create_task(self._run_inline_step(child_id, child, child_state, runtime_ctx)))
        errors = []
        results_states: list[FlowState] = []
        for t in asyncio.as_completed(tasks):
            try:
                child_state = await t
                results_states.append(child_state)
            except Exception as exc:
                errors.append(exc)
                if fail_fast:
                    for pending in tasks:
                        if not pending.done():
                            pending.cancel()
                    break
        if errors:
            raise errors[0]
        # Merge branch states back into parent.
        self._merge_branch_states(state, branch_ids, results_states)
        return {"parallel": branch_ids}

    async def _execute_for_each(self, node: FlowNode, state: FlowState, runtime_ctx: FlowRuntimeContext):
        config = node.config if isinstance(node.config, dict) else {}
        iterable_expr = config.get("iterable_expr")
        items_path = config.get("items_path")
        var_name = config.get("var_name")
        body = config.get("body") or []

        evaluator = self._build_evaluator(state, runtime_ctx)
        items_val = config.get("items")
        items: list[Any] = []
        if iterable_expr is not None:
            iterable_value = evaluator.evaluate(iterable_expr)
            if iterable_value is None:
                items = []
            elif isinstance(iterable_value, (list, tuple)):
                items = list(iterable_value)
            else:
                raise Namel3ssError("Loop iterable must be a list/array-like")
        elif items_path:
            iterable_value = state.get(items_path, []) or []
            if iterable_value is None:
                items = []
            elif isinstance(iterable_value, (list, tuple)):
                items = list(iterable_value)
            else:
                raise Namel3ssError("Loop iterable must be a list/array-like")
        elif items_val is not None:
            if isinstance(items_val, (list, tuple)):
                items = list(items_val)
            else:
                raise Namel3ssError("Loop iterable must be a list/array-like")
        else:
            items = []

        env = state.variables or runtime_ctx.variables or VariableEnvironment()
        had_prev = bool(var_name and env.has(var_name))
        prev_val = env.resolve(var_name) if had_prev and var_name else None
        items_meta: list[dict[str, Any]] = []

        try:
            for idx, item in enumerate(items):
                before_data = dict(state.data)
                if var_name:
                    if env.has(var_name):
                        env.assign(var_name, item)
                    else:
                        env.declare(var_name, item)
                    state.set(var_name, item)
                state.set("loop.item", item)
                await self._run_inline_sequence(f"{node.id}.{idx}", body, state, runtime_ctx, loop_item=item)
                delta = {k: v for k, v in state.data.items() if before_data.get(k) != v}
                items_meta.append(delta)
                if state.context.get("__redirect_flow__"):
                    break
        finally:
            if var_name:
                if had_prev:
                    env.assign(var_name, prev_val)
                    state.set(var_name, prev_val)
                else:
                    env.remove(var_name)
                    state.data.pop(var_name, None)
            state.data.pop("loop.item", None)
        state.set(f"step.{node.id}.items", items_meta)
        return {"for_each": len(items)}

    async def _execute_try_catch(self, node: FlowNode, state: FlowState, runtime_ctx: FlowRuntimeContext):
        try_steps = node.config.get("try_steps") or node.config.get("try") or []
        catch_steps = node.config.get("catch_steps") or node.config.get("catch") or []
        finally_steps = node.config.get("finally_steps") or node.config.get("finally") or []
        try_state = state.copy()
        try:
            await self._run_inline_sequence(f"{node.id}.try", try_steps, try_state, runtime_ctx)
            state.data.update(try_state.data)
            state.errors.extend(try_state.errors)
            return {"try": "ok"}
        except Exception:
            catch_state = state.copy()
            await self._run_inline_sequence(f"{node.id}.catch", catch_steps, catch_state, runtime_ctx)
            state.data.update(catch_state.data)
            state.errors.extend(catch_state.errors)
            return {"try": "failed"}
        finally:
            finally_state = state.copy()
            if finally_steps:
                await self._run_inline_sequence(f"{node.id}.finally", finally_steps, finally_state, runtime_ctx)
                state.data.update(finally_state.data)
                state.errors.extend(finally_state.errors)

    async def _run_inline_step(
        self, step_id: str, step_def: dict, state: FlowState, runtime_ctx: FlowRuntimeContext
    ) -> FlowState:
        node = FlowNode(
            id=step_id,
            kind=step_def.get("kind", "function"),
            config=step_def.get("config") or step_def,
            next_ids=[],
        )
        result = await self._execute_with_timing(node, state, runtime_ctx)
        if result and runtime_ctx.step_results is not None:
            runtime_ctx.step_results.append(result)
        return state

    async def _run_inline_sequence(
        self,
        prefix: str,
        steps: list[dict],
        state: FlowState,
        runtime_ctx: FlowRuntimeContext,
        loop_item: Any | None = None,
    ) -> FlowState:
        if loop_item is not None:
            state.set("loop.item", loop_item)
        for idx, step in enumerate(steps):
            step_id = step.get("id") or step.get("name") or f"{prefix}.step{idx}"
            state = await self._run_inline_step(step_id, step, state, runtime_ctx)
            if state.context.get("__redirect_flow__"):
                break
        return state

    async def _execute_ir_if(self, stmt: IRIf, state: FlowState, runtime_ctx: FlowRuntimeContext, prefix: str) -> None:
        env = state.variables or runtime_ctx.variables or VariableEnvironment()
        for idx, br in enumerate(stmt.branches):
            result, candidate_binding = self._eval_condition_with_binding(br.condition, state, runtime_ctx)
            label = br.label or f"branch-{idx}"
            if br.label == "unless":
                result = not result
            if not result:
                continue
            previous_binding = None
            had_prev = False
            if br.binding:
                if env.has(br.binding):
                    had_prev = True
                    previous_binding = env.resolve(br.binding)
                    env.assign(br.binding, candidate_binding)
                else:
                    env.declare(br.binding, candidate_binding)
                state.set(br.binding, candidate_binding)
            for action in br.actions:
                await self._execute_statement(action, state, runtime_ctx, f"{prefix}.{label}")
            if br.binding:
                if had_prev:
                    env.assign(br.binding, previous_binding)
                    state.set(br.binding, previous_binding)
                else:
                    env.remove(br.binding)
                    state.data.pop(br.binding, None)
            break

    async def _emit_state_change(
        self,
        runtime_ctx: FlowRuntimeContext,
        flow_name: str | None,
        step_name: str | None,
        path: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        if not runtime_ctx.stream_callback:
            return
        event: StreamEvent = {
            "kind": "state_change",
            "flow": flow_name or "",
            "step": step_name or "",
            "path": path,
            "old_value": old_value,
            "new_value": new_value,
        }
        try:
            result = runtime_ctx.stream_callback(event)
            if inspect.isawaitable(result):
                await result
        except Exception:
            # Streaming failures should not crash the flow execution path.
            return

    async def _execute_statement(self, stmt: IRStatement, state: FlowState, runtime_ctx: FlowRuntimeContext, prefix: str, allow_return: bool = False) -> Any:
        env = state.variables or runtime_ctx.variables or VariableEnvironment()
        evaluator = self._build_evaluator(state, runtime_ctx)
        if isinstance(stmt, IRLet):
            value = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
            env.declare(stmt.name, value)
            state.set(stmt.name, value)
            state.set("last_output", value)
            return value
        if isinstance(stmt, IRSet):
            # Support state.<field> assignment
            if stmt.name.startswith("state."):
                field = stmt.name[len("state.") :]
                if not field:
                    raise Namel3ssError("N3F-410: set statements must update 'state.<field>'.")
                old_value = state.get(field)
                value = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
                state.set(stmt.name, value)
                state.set(field, value)
                state.set("last_output", value)
                await self._emit_state_change(
                    runtime_ctx,
                    flow_name=state.context.get("flow_name"),
                    step_name=prefix.split(".")[0] if prefix else None,
                    path=field,
                    old_value=old_value,
                    new_value=value,
                )
                return value
            if not env.has(stmt.name):
                raise Namel3ssError(f"Variable '{stmt.name}' is not defined")
            value = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
            env.assign(stmt.name, value)
            state.set(stmt.name, value)
            state.set("last_output", value)
            return value
        if isinstance(stmt, IRIf):
            await self._execute_ir_if(stmt, state, runtime_ctx, prefix)
            return state.get("last_output")
        if isinstance(stmt, IRTryCatch):
            try:
                last_output = None
                for body_stmt in stmt.try_body:
                    last_output = await self._execute_statement(body_stmt, state, runtime_ctx, f"{prefix}.try", allow_return=allow_return)
                return last_output
            except Exception as exc:  # pragma: no cover - evaluated via tests
                err_obj = {"kind": exc.__class__.__name__, "message": str(exc)}
                had_prev = env.has(stmt.error_name)
                prev_val = env.resolve(stmt.error_name) if had_prev else None
                if had_prev:
                    env.assign(stmt.error_name, err_obj)
                else:
                    env.declare(stmt.error_name, err_obj)
                state.set(stmt.error_name, err_obj)
                state.set("last_output", err_obj)
                try:
                    for body_stmt in stmt.catch_body:
                        await self._execute_statement(body_stmt, state, runtime_ctx, f"{prefix}.catch", allow_return=allow_return)
                finally:
                    if had_prev:
                        env.assign(stmt.error_name, prev_val)
                        state.set(stmt.error_name, prev_val)
                    else:
                        env.remove(stmt.error_name)
                        state.data.pop(stmt.error_name, None)
                return state.get("last_output")
        if isinstance(stmt, IRForEach):
            iterable_val = evaluator.evaluate(stmt.iterable) if stmt.iterable is not None else None
            if not isinstance(iterable_val, list):
                raise Namel3ssError("N3-3400: for-each loop requires a list value")
            had_prev = env.has(stmt.var_name)
            prev_val = env.resolve(stmt.var_name) if had_prev else None
            declared_new = not had_prev
            for idx, item in enumerate(iterable_val):
                if had_prev or not declared_new:
                    env.assign(stmt.var_name, item)
                else:
                    env.declare(stmt.var_name, item)
                    declared_new = False
                state.set(stmt.var_name, item)
                for body_stmt in stmt.body:
                    await self._execute_statement(body_stmt, state, runtime_ctx, f"{prefix}.foreach{idx}", allow_return=allow_return)
                    if state.context.get("__awaiting_input__"):
                        break
                if state.context.get("__awaiting_input__"):
                    break
            if had_prev:
                env.assign(stmt.var_name, prev_val)
                state.set(stmt.var_name, prev_val)
            else:
                env.remove(stmt.var_name)
                state.data.pop(stmt.var_name, None)
            return state.get("last_output")
        if isinstance(stmt, IRRepeatUpTo):
            count_val = evaluator.evaluate(stmt.count) if stmt.count is not None else 0
            try:
                count_num = int(count_val)
            except Exception:
                raise Namel3ssError("N3-3401: repeat-up-to requires numeric count")
            if count_num < 0:
                raise Namel3ssError("N3-3402: loop count must be non-negative")
            for idx in range(count_num):
                for body_stmt in stmt.body:
                    await self._execute_statement(body_stmt, state, runtime_ctx, f"{prefix}.repeat{idx}", allow_return=allow_return)
                    if state.context.get("__awaiting_input__"):
                        break
                if state.context.get("__awaiting_input__"):
                    break
            return state.get("last_output")
        if isinstance(stmt, IRRetry):
            count_val = evaluator.evaluate(stmt.count) if stmt.count is not None else 0
            try:
                attempts = int(count_val)
            except Exception:
                raise Namel3ssError("N3-4500: retry requires numeric max attempts")
            if attempts < 1:
                raise Namel3ssError("N3-4501: retry max attempts must be at least 1")
            last_output = None
            for attempt in range(attempts):
                try:
                    for body_stmt in stmt.body:
                        last_output = await self._execute_statement(body_stmt, state, runtime_ctx, f"{prefix}.retry{attempt}", allow_return=allow_return)
                        if state.context.get("__awaiting_input__"):
                            break
                    if state.context.get("__awaiting_input__"):
                        break
                    # success if no exception and result not error-like
                    if not self._is_error_result(last_output):
                        break
                    if attempt + 1 == attempts:
                        break
                except Namel3ssError:
                    if attempt + 1 == attempts:
                        raise
                    continue
            state.set("last_output", last_output)
            return last_output
        if isinstance(stmt, IRMatch):
            target_val = evaluator.evaluate(stmt.target) if stmt.target is not None else None
            for br in stmt.branches:
                if self._match_branch(br, target_val, evaluator, state):
                    for act in br.actions:
                        await self._execute_statement(act, state, runtime_ctx, f"{prefix}.match", allow_return=allow_return)
                        if state.context.get("__awaiting_input__"):
                            break
                    break
            return state.get("last_output")
        if isinstance(stmt, IRReturn):
            if not allow_return:
                raise Namel3ssError("N3-6002: return used outside helper")
            value = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
            raise ReturnSignal(value)
        if isinstance(stmt, IRAskUser):
            provided = self._resolve_provided_input(stmt.var_name, runtime_ctx, state)
            if provided is not None:
                self._assign_variable(stmt.var_name, provided, state)
                return provided
            request = {
                "type": "ask",
                "name": stmt.var_name,
                "label": stmt.label,
                "validation": self._validation_to_dict(stmt.validation, evaluator),
            }
            state.inputs.append(request)
            state.context["__awaiting_input__"] = True
            return None
        if isinstance(stmt, IRForm):
            provided = self._resolve_provided_input(stmt.name, runtime_ctx, state)
            if isinstance(provided, dict):
                self._assign_variable(stmt.name, provided, state)
                return provided
            field_defs = [
                {
                    "label": f.label,
                    "name": f.name,
                    "validation": self._validation_to_dict(f.validation, evaluator),
                }
                for f in stmt.fields
            ]
            request = {
                "type": "form",
                "name": stmt.name,
                "label": stmt.label,
                "fields": field_defs,
            }
            state.inputs.append(request)
            state.context["__awaiting_input__"] = True
            return None
        if isinstance(stmt, IRLog):
            meta_val = evaluator.evaluate(stmt.metadata) if stmt.metadata is not None else None
            entry = self._build_log_entry(stmt.level, stmt.message, meta_val, state)
            state.logs.append(entry)
            if runtime_ctx.tracer:
                runtime_ctx.tracer.record_flow_event("log", entry)
            return state.get("last_output")
        if isinstance(stmt, IRNote):
            entry = self._build_note_entry(stmt.message, state)
            state.notes.append(entry)
            if runtime_ctx.tracer:
                runtime_ctx.tracer.record_flow_event("note", entry)
            return state.get("last_output")
        if isinstance(stmt, IRCheckpoint):
            entry = self._build_checkpoint_entry(stmt.label, state)
            state.checkpoints.append(entry)
            if runtime_ctx.tracer:
                runtime_ctx.tracer.record_flow_event("checkpoint", entry)
            return state.get("last_output")
        if isinstance(stmt, IRAction):
            cfg = {
                "kind": stmt.kind,
                "target": stmt.target,
                "step_name": f"{prefix}.{stmt.target}",
                "reason": "script",
            }
            if stmt.message is not None:
                cfg["params"] = {"message": stmt.message}
            await self._run_inline_sequence(prefix, [cfg], state, runtime_ctx)
            return state.get("last_output")
        raise Namel3ssError(f"Unsupported statement '{type(stmt).__name__}' in script")

    async def _execute_script(self, statements: list[IRStatement] | None, state: FlowState, runtime_ctx: FlowRuntimeContext, step_id: str) -> Any:
        last_val: Any = None
        for idx, stmt in enumerate(statements or []):
            last_val = await self._execute_statement(stmt, state, runtime_ctx, f"{step_id}.stmt{idx}")
            if state.context.get("__awaiting_input__"):
                break
        return last_val

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

        timeout = node.config.get("timeout_seconds")
        start = time.monotonic()
        if runtime_ctx.event_logger:
            try:
                runtime_ctx.event_logger.log(
                    {
                        "kind": "step",
                        "event_type": "start",
                        "flow_name": state.context.get("flow_name"),
                        "step_name": node.id,
                        "status": "running",
                    }
                )
            except Exception:
                pass
        async def run_inner():
            if node.config.get("simulate_duration"):
                await asyncio.sleep(float(node.config["simulate_duration"]))
            return await self._execute_node(node, state, runtime_ctx)

        try:
            if timeout:
                result = await asyncio.wait_for(run_inner(), timeout=timeout)
            else:
                result = await run_inner()
        except Exception as exc:
            duration = time.monotonic() - start
            if runtime_ctx.event_logger:
                try:
                    runtime_ctx.event_logger.log(
                        {
                            "kind": "step",
                            "event_type": "error",
                            "flow_name": state.context.get("flow_name"),
                            "step_name": node.id,
                            "status": "error",
                            "message": str(exc),
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
                        "step_name": node.id,
                        "status": "success",
                    }
                )
            except Exception:
                pass
        return result

    def _extract_duration(self, exc: Exception) -> float:
        if isinstance(exc, TimedStepError):
            return exc.duration
        return 0.0

    def _extract_cost(self, output: Any) -> float:
        if output is None:
            return 0.0
        if isinstance(output, dict):
            if "cost" in output and isinstance(output["cost"], (int, float)):
                return float(output["cost"])
            if "provider_result" in output:
                prov = output["provider_result"]
                if isinstance(prov, dict) and "cost" in prov:
                    try:
                        return float(prov["cost"])
                    except Exception:
                        return 0.0
        if hasattr(output, "cost"):
            try:
                return float(output.cost)
            except Exception:
                return 0.0
        return 0.0

    # -------- Condition helpers --------
    def _expr_to_str(self, expr: ast_nodes.Expr | None) -> str:
        if expr is None:
            return "<otherwise>"
        if isinstance(expr, ast_nodes.Identifier):
            return expr.name
        if isinstance(expr, ast_nodes.VarRef):
            return expr.name or ".".join([expr.root, *expr.path])
        if isinstance(expr, ast_nodes.Literal):
            return repr(expr.value)
        if isinstance(expr, ast_nodes.UnaryOp):
            return f"{expr.op} {self._expr_to_str(expr.operand)}"
        if isinstance(expr, ast_nodes.BinaryOp):
            return f"{self._expr_to_str(expr.left)} {expr.op} {self._expr_to_str(expr.right)}"
        if isinstance(expr, ast_nodes.PatternExpr):
            pairs = ", ".join(f"{p.key}: {self._expr_to_str(p.value)}" for p in expr.pairs)
            return f"{expr.subject.name} matches {{{pairs}}}"
        if isinstance(expr, ast_nodes.RuleGroupRefExpr):
            if expr.condition_name:
                return f"{expr.group_name}.{expr.condition_name}"
            return expr.group_name
        return str(expr)

    def _resolve_identifier(self, name: str, state: FlowState, runtime_ctx: FlowRuntimeContext | None) -> tuple[bool, Any]:
        env = getattr(state, "variables", None)
        if env and env.has(name):
            return True, env.resolve(name)
        if name == "user":
            if runtime_ctx and getattr(runtime_ctx, "user_context", None) is not None:
                return True, runtime_ctx.user_context
            return True, state.context.get("user")
        if name.startswith("user."):
            user_ctx = (runtime_ctx.user_context if runtime_ctx else None) or state.context.get("user") or {}
            parts = name.split(".")[1:]
            value: Any = user_ctx
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = getattr(value, part, None)
            return True, value
        if name == "secret":
            secrets_mgr = (runtime_ctx.secrets if runtime_ctx else None) or self.secrets
            return True, secrets_mgr
        if name.startswith("secret."):
            secrets_mgr = (runtime_ctx.secrets if runtime_ctx else None) or self.secrets
            key = name[len("secret.") :]
            if secrets_mgr:
                return True, secrets_mgr.get(key)
            return True, None
        if name == "state":
            return True, state.data
        if name.startswith("state."):
            field = name[len("state.") :]
            if field and field in state.data:
                return True, state.get(field)
        if name in state.data:
            return True, state.get(name)
        if env and "." in name:
            parts = name.split(".")
            if env.has(parts[0]):
                value: Any = env.resolve(parts[0])
                for part in parts[1:]:
                    if isinstance(value, dict) and part in value:
                        value = value.get(part)
                    elif hasattr(value, part):
                        value = getattr(value, part, None)
                    else:
                        return False, None
                return True, value
        parts = name.split(".")
        value: Any = None
        found = False
        if parts[0] in state.data:
            value = state.get(parts[0])
            found = True
        elif parts[0] in state.context:
            value = state.context.get(parts[0])
            found = True
        elif runtime_ctx and runtime_ctx.frames and parts[0] in getattr(runtime_ctx.frames, "frames", {}):
            value = runtime_ctx.frames.get_rows(parts[0])
            found = True
        else:
            return False, None
        for part in parts[1:]:
            if isinstance(value, dict) and part in value:
                value = value.get(part)
                found = True
            elif hasattr(value, part):
                value = getattr(value, part, None)
                found = True
            else:
                return False, None
        return found, value

    def _call_helper(self, name: str, args: list[Any], state: FlowState, runtime_ctx: FlowRuntimeContext | None) -> Any:
        helper = runtime_ctx.program.helpers.get(name) if runtime_ctx and runtime_ctx.program else None
        if not helper:
            raise Namel3ssError(f"N3-6000: unknown helper '{name}'")
        if len(args) != len(helper.params):
            raise Namel3ssError("N3-6001: wrong number of arguments for helper")
        env = (state.variables or VariableEnvironment()).clone()
        saved_env = state.variables
        for param, arg in zip(helper.params, args):
            if env.has(param):
                env.assign(param, arg)
            else:
                env.declare(param, arg)
            state.set(param, arg)
        state.variables = env
        evaluator = self._build_evaluator(state, runtime_ctx)
        try:
            for stmt in helper.body:
                if isinstance(stmt, IRLet):
                    val = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
                    env.declare(stmt.name, val)
                    state.set(stmt.name, val)
                elif isinstance(stmt, IRSet):
                    if not env.has(stmt.name):
                        raise Namel3ssError(f"Variable '{stmt.name}' is not defined")
                    val = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
                    env.assign(stmt.name, val)
                    state.set(stmt.name, val)
                elif isinstance(stmt, IRReturn):
                    return evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
                else:
                    raise Namel3ssError("Helper bodies support let/set/return statements in this phase")
        finally:
            state.variables = saved_env
        return None

    def _is_error_result(self, value: Any) -> bool:
        if isinstance(value, Exception):
            return True
        if isinstance(value, dict):
            if value.get("error") is not None:
                return True
            if "success" in value and value.get("success") is False:
                return True
        return False

    def _extract_success_payload(self, value: Any) -> Any:
        if isinstance(value, dict):
            if "result" in value:
                return value.get("result")
            if "value" in value:
                return value.get("value")
        return value

    def _extract_error_payload(self, value: Any) -> Any:
        if isinstance(value, dict) and "error" in value:
            return value.get("error")
        return value

    def _match_branch(self, br: IRMatchBranch, target_val: Any, evaluator: ExpressionEvaluator, state: FlowState) -> bool:
        pattern = br.pattern
        env = state.variables or VariableEnvironment()
        if isinstance(pattern, ast_nodes.SuccessPattern):
            if self._is_error_result(target_val):
                return False
            if pattern.binding:
                if env.has(pattern.binding):
                    env.assign(pattern.binding, self._extract_success_payload(target_val))
                else:
                    env.declare(pattern.binding, self._extract_success_payload(target_val))
                state.set(pattern.binding, self._extract_success_payload(target_val))
            return True
        if isinstance(pattern, ast_nodes.ErrorPattern):
            if not self._is_error_result(target_val):
                return False
            if pattern.binding:
                if env.has(pattern.binding):
                    env.assign(pattern.binding, self._extract_error_payload(target_val))
                else:
                    env.declare(pattern.binding, self._extract_error_payload(target_val))
                state.set(pattern.binding, self._extract_error_payload(target_val))
            return True
        if pattern is None:
            return True
        try:
            pat_val = evaluator.evaluate(pattern)
        except Exception as exc:
            raise Namel3ssError(str(exc))
        if isinstance(pat_val, bool):
            return bool(pat_val)
        return target_val == pat_val

    def _resolve_provided_input(self, name: str, runtime_ctx: FlowRuntimeContext, state: FlowState) -> Any:
        env = state.variables or VariableEnvironment()
        if env.has(name):
            try:
                return env.resolve(name)
            except Exception:
                return None
        ctx_inputs = {}
        exec_ctx = getattr(runtime_ctx, "execution_context", None)
        if exec_ctx and isinstance(getattr(exec_ctx, "metadata", None), dict):
            ctx_inputs = exec_ctx.metadata.get("inputs", {}) or {}
        if isinstance(ctx_inputs, dict) and name in ctx_inputs:
            return ctx_inputs.get(name)
        return None

    def _assign_variable(self, name: str, value: Any, state: FlowState) -> None:
        env = state.variables or VariableEnvironment()
        if env.has(name):
            env.assign(name, value)
        else:
            env.declare(name, value)
        state.variables = env
        state.set(name, value)

    def _validation_to_dict(self, validation: ast_nodes.InputValidation | None, evaluator: ExpressionEvaluator) -> dict | None:
        if not validation:
            return None
        data: dict[str, Any] = {}
        if validation.field_type:
            data["type"] = validation.field_type
        if validation.min_expr is not None:
            try:
                data["min"] = evaluator.evaluate(validation.min_expr)
            except Exception:
                data["min"] = None
        if validation.max_expr is not None:
            try:
                data["max"] = evaluator.evaluate(validation.max_expr)
            except Exception:
                data["max"] = None
        return data or None

    def _build_log_entry(self, level: str, message: str, metadata: Any, state: FlowState) -> dict:
        return {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "metadata": metadata,
        }

    def _build_note_entry(self, message: str, state: FlowState) -> dict:
        return {"timestamp": time.time(), "message": message}

    def _build_checkpoint_entry(self, label: str, state: FlowState) -> dict:
        return {"timestamp": time.time(), "label": label}

    def _build_evaluator(
        self, state: FlowState, runtime_ctx: FlowRuntimeContext | None, env_override: VariableEnvironment | None = None
    ) -> ExpressionEvaluator:
        env = env_override or getattr(state, "variables", None) or getattr(runtime_ctx, "variables", None) or VariableEnvironment()
        return ExpressionEvaluator(
            env,
            resolver=lambda name: self._resolve_identifier(name, state, runtime_ctx),
            rulegroup_resolver=lambda expr: self._eval_rulegroup(expr, state, runtime_ctx) if runtime_ctx else (False, None),
            helper_resolver=lambda name, args: self._call_helper(name, args, state, runtime_ctx),
        )

    def _http_json_request(
        self, method: str, url: str, headers: dict[str, str], body: bytes | None
    ) -> tuple[int, dict[str, str], str]:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:  # pragma: no cover - exercised via monkeypatch in tests
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                status = resp.getcode()
                resp_headers = dict(resp.headers.items())
                return status, resp_headers, text
        except urllib.error.HTTPError as exc:  # pragma: no cover - fallback
            text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            resp_headers = dict(exc.headers.items()) if exc.headers else {}
            return exc.code, resp_headers, text

    async def _execute_tool_call(self, node, state: FlowState, runtime_ctx: FlowRuntimeContext):
        target = node.config.get("target") if isinstance(node.config, dict) else None
        tool_cfg = runtime_ctx.tool_registry.get(target)
        if not tool_cfg:
            raise Namel3ssError(f"N3L-1400: Tool '{target}' is not declared.")

        evaluator = self._build_evaluator(state, runtime_ctx)
        params = node.config.get("params") or {}
        args_exprs = params.get("input") or params.get("args") or {}
        arg_values: dict[str, Any] = {}
        if isinstance(args_exprs, dict):
            for k, expr in args_exprs.items():
                try:
                    arg_values[k] = evaluator.evaluate(expr)
                except Exception as exc:
                    raise Namel3ssError(f"Failed to evaluate input '{k}' for tool '{tool_cfg.name}': {exc}") from exc

        required_inputs = list(getattr(tool_cfg, "input_fields", []) or [])
        missing_inputs = [field for field in required_inputs if field not in arg_values]
        if missing_inputs:
            raise Namel3ssError(
                f"N3F-965: Missing arg '{missing_inputs[0]}' for tool '{tool_cfg.name}'."
            )

        if hasattr(tool_cfg, "calls"):
            payload = arg_values if arg_values else {"message": state.get("slug")}
            try:
                tool_cfg.calls.append(payload)
            except Exception:
                pass

        if not hasattr(tool_cfg, "url_expr") and not hasattr(tool_cfg, "url_template"):
            if callable(getattr(tool_cfg, "execute", None)):
                return tool_cfg.execute(arg_values)
            if callable(tool_cfg):
                return tool_cfg(arg_values)
            return {"result": arg_values}

        env = state.variables.clone() if state.variables else VariableEnvironment()
        if env.has("input"):
            env.assign("input", arg_values)
        else:
            env.declare("input", arg_values)
        tool_evaluator = self._build_evaluator(state, runtime_ctx, env_override=env)

        def _eval_value(expr: Any) -> Any:
            if isinstance(expr, ast_nodes.Expr):
                return tool_evaluator.evaluate(expr)
            return expr

        method = (getattr(tool_cfg, "method", "GET") or "GET").upper()

        url_value: Any = None
        if getattr(tool_cfg, "url_expr", None) is not None:
            url_value = _eval_value(tool_cfg.url_expr)
        else:
            url_template = getattr(tool_cfg, "url_template", None)
            if url_template:
                try:
                    url_value = url_template.format(**{k: "" if v is None else str(v) for k, v in arg_values.items()})
                except KeyError as exc:
                    missing = str(exc).strip("'\"")
                    raise Namel3ssError(
                        f"N3F-965: Missing arg '{missing}' for tool '{tool_cfg.name}' url."
                    )
        if not url_value:
            raise Namel3ssError(f"N3F-965: Tool '{tool_cfg.name}' is missing a resolved URL.")
        url_str = str(url_value)

        headers: dict[str, str] = {}
        for hk, h_expr in (getattr(tool_cfg, "headers", {}) or {}).items():
            value = _eval_value(h_expr)
            if value is None:
                continue
            headers[hk] = "" if value is None else str(value)

        query_exprs = getattr(tool_cfg, "query_params", {}) or {}
        if query_exprs:
            parsed = urllib.parse.urlparse(url_str)
            query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            for qk, q_expr in query_exprs.items():
                val = _eval_value(q_expr)
                if val is None:
                    continue
                if isinstance(val, list):
                    for item in val:
                        query_items.append((qk, "" if item is None else str(item)))
                else:
                    query_items.append((qk, "" if val is None else str(val)))
            url_str = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query_items, doseq=True)))

        body_payload: Any = None
        body_fields = getattr(tool_cfg, "body_fields", {}) or {}
        if body_fields:
            body_payload = {}
            for bk, b_expr in body_fields.items():
                body_payload[bk] = _eval_value(b_expr)
        elif getattr(tool_cfg, "body_template", None) is not None:
            body_payload = tool_evaluator.evaluate(tool_cfg.body_template)

        body_bytes: bytes | None = None
        if body_payload is not None:
            if isinstance(body_payload, (dict, list)):
                body_bytes = json.dumps(body_payload).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")
            elif isinstance(body_payload, str):
                body_bytes = body_payload.encode("utf-8")
            else:
                body_bytes = json.dumps(body_payload).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")

        if runtime_ctx.event_logger:
            try:
                runtime_ctx.event_logger.log(
                    {
                        "kind": "tool",
                        "event_type": "start",
                        "tool": tool_cfg.name,
                        "step": node.id,
                        "flow_name": state.context.get("flow_name"),
                        "status": "running",
                        "method": method,
                        "url": url_str,
                    }
                )
            except Exception:
                pass

        try:
            status, response_headers, raw_text = self._http_json_request(method, url_str, headers, body_bytes)
        except urllib.error.URLError as exc:
            result = {
                "ok": False,
                "status": None,
                "data": None,
                "headers": {},
                "error": f"Network error: {getattr(exc, 'reason', exc)}",
            }
            if runtime_ctx.event_logger:
                try:
                    runtime_ctx.event_logger.log(
                        {
                            "kind": "tool",
                            "event_type": "error",
                            "tool": tool_cfg.name,
                            "step": node.id,
                            "flow_name": state.context.get("flow_name"),
                            "status": "error",
                            "message": result["error"],
                        }
                    )
                except Exception:
                    pass
            return result

        parsed_body: Any = None
        if raw_text:
            try:
                parsed_body = json.loads(raw_text)
            except ValueError:
                parsed_body = raw_text

        ok = 200 <= (status or 0) < 300
        result = {
            "ok": ok,
            "status": status,
            "data": parsed_body,
            "headers": response_headers,
        }
        if not ok:
            result["error"] = f"HTTP {status}"

        if runtime_ctx.event_logger:
            try:
                runtime_ctx.event_logger.log(
                    {
                        "kind": "tool",
                        "event_type": "end" if ok else "error",
                        "tool": tool_cfg.name,
                        "step": node.id,
                        "flow_name": state.context.get("flow_name"),
                        "status": "success" if ok else "error",
                        "status_code": status,
                        "method": method,
                        "url": url_str,
                        "ok": ok,
                    }
                )
            except Exception:
                pass
        return result

    def _evaluate_expr_dict(
        self,
        entries: dict[str, ast_nodes.Expr] | None,
        evaluator: ExpressionEvaluator,
        step_name: str,
        block_name: str,
    ) -> dict[str, Any]:
        if not isinstance(entries, dict):
            return {}
        values: dict[str, Any] = {}
        for key, expr in entries.items():
            try:
                values[key] = evaluator.evaluate(expr) if isinstance(expr, ast_nodes.Expr) else expr
            except Exception as exc:
                raise Namel3ssError(
                    f"Failed to evaluate '{key}' inside '{block_name}' for step '{step_name}': {exc}"
                ) from exc
        return values

    def _resolve_record_default_value(self, field) -> Any:
        if getattr(field, "default", None) == "now":
            return datetime.utcnow().isoformat()
        return field.default

    def _coerce_record_value(self, record_name: str, field, value: Any, step_name: str) -> Any:
        if value is None:
            return None
        ftype = getattr(field, "type", "string")
        try:
            if ftype in {"string", "text"}:
                return "" if value is None else str(value)
            if ftype == "int":
                if isinstance(value, bool):
                    return int(value)
                if isinstance(value, (int, float)):
                    if isinstance(value, float) and not value.is_integer():
                        raise ValueError("cannot truncate non-integer float")
                    return int(value)
                return int(str(value))
            if ftype == "float":
                if isinstance(value, bool):
                    return float(int(value))
                if isinstance(value, (int, float)):
                    return float(value)
                return float(str(value))
            if ftype == "bool":
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    normalized = value.strip().lower()
                    if normalized in {"true", "false"}:
                        return normalized == "true"
                raise ValueError("expected boolean literal")
            if ftype == "uuid":
                text = str(value)
                try:
                    UUID(text)
                except Exception:
                    # Treat any stringable value as acceptable; upstream validation is lenient.
                    return text
                return text
            if ftype == "datetime":
                if isinstance(value, datetime):
                    return value.isoformat()
                return str(value)
        except Exception as exc:
            raise Namel3ssError(
                f"Field '{field.name}' on record '{record_name}' could not be coerced to type '{ftype}': {exc}"
            ) from exc
        return value

    def _prepare_record_values(
        self,
        record,
        values: dict[str, Any],
        step_name: str,
        include_defaults: bool,
        enforce_required: bool,
    ) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, raw in values.items():
            field = record.fields.get(key)
            if not field:
                raise Namel3ssError(
                    f"Record '{record.name}' has no field named '{key}' (step '{step_name}')."
                )
            coerced = self._coerce_record_value(record.name, field, raw, step_name)
            if coerced is None and enforce_required and (field.required or field.primary_key):
                raise Namel3ssError(
                    f"N3L-1502: Field '{key}' cannot be null when creating record '{record.name}'."
                )
            normalized[key] = coerced
        if include_defaults:
            for key, field in record.fields.items():
                if key in normalized:
                    continue
                if field.default is not None:
                    normalized[key] = self._resolve_record_default_value(field)
                elif enforce_required and field.required:
                    raise Namel3ssError(
                        f"N3L-1502: Step '{step_name}' must provide field '{key}' for record '{record.name}'."
                    )
        return normalized

    def _evaluate_limit_expr(
        self,
        expr: ast_nodes.Expr | None,
        evaluator: ExpressionEvaluator,
        step_name: str,
    ) -> int | None:
        if expr is None:
            return None
        try:
            value = evaluator.evaluate(expr) if isinstance(expr, ast_nodes.Expr) else expr
        except Exception as exc:
            raise Namel3ssError(f"Failed to evaluate 'limit' for step '{step_name}': {exc}") from exc
        if value is None:
            return None
        if not isinstance(value, (int, float)):
            raise Namel3ssError(
                f"'limit' must evaluate to a number in step '{step_name}'."
            )
        limit = int(value)
        if limit < 0:
            return 0
        return limit

    def _execute_record_step(
        self,
        kind: str,
        record,
        params: dict[str, Any],
        evaluator: ExpressionEvaluator,
        runtime_ctx: FlowRuntimeContext,
        step_name: str,
    ) -> Any:
        frames = runtime_ctx.frames
        if frames is None:
            raise Namel3ssError("Frame registry unavailable for record operations.")
        frame_name = getattr(record, "frame", None)
        if not frame_name:
            raise Namel3ssError(
                f"Record '{record.name}' is missing an associated frame."
            )
        if kind == "db_create":
            values = self._evaluate_expr_dict(params.get("values"), evaluator, step_name, "values")
            normalized = self._prepare_record_values(
                record,
                values,
                step_name,
                include_defaults=True,
                enforce_required=True,
            )
            frames.insert(frame_name, normalized)
            return dict(normalized)
        if kind == "db_get":
            by_id_values = self._evaluate_expr_dict(params.get("by_id"), evaluator, step_name, "by id")
            where_values = self._evaluate_expr_dict(params.get("where"), evaluator, step_name, "where")
            filters: dict[str, Any] = {}
            used_primary = False
            if record.primary_key and record.primary_key in by_id_values:
                pk_field = record.fields.get(record.primary_key)
                if pk_field:
                    filters[record.primary_key] = self._coerce_record_value(
                        record.name,
                        pk_field,
                        by_id_values[record.primary_key],
                        step_name,
                    )
                    used_primary = True
            elif where_values:
                for key, raw in where_values.items():
                    field = record.fields.get(key)
                    if not field:
                        raise Namel3ssError(
                            f"Record '{record.name}' has no field named '{key}' (step '{step_name}')."
                        )
                    filters[key] = self._coerce_record_value(record.name, field, raw, step_name)
            rows = frames.query(frame_name, filters)
            if used_primary:
                return dict(rows[0]) if rows else None
            limit_value = self._evaluate_limit_expr(params.get("limit"), evaluator, step_name)
            if limit_value is not None:
                rows = rows[: limit_value or 0]
            return [dict(row) for row in rows]
        if kind == "db_update":
            by_id_values = self._evaluate_expr_dict(params.get("by_id"), evaluator, step_name, "by id")
            if not record.primary_key or record.primary_key not in by_id_values:
                raise Namel3ssError(
                    f"Step '{step_name}' must include primary key '{record.primary_key}' inside 'by id'."
                )
            pk_field = record.fields.get(record.primary_key)
            filters = {
                record.primary_key: self._coerce_record_value(
                    record.name,
                    pk_field,
                    by_id_values[record.primary_key],
                    step_name,
                )
            }
            set_values = self._evaluate_expr_dict(params.get("set"), evaluator, step_name, "set")
            updates = self._prepare_record_values(
                record,
                set_values,
                step_name,
                include_defaults=False,
                enforce_required=False,
            )
            rows = frames.query(frame_name, filters)
            if not rows:
                return None
            for row in rows:
                row.update(updates)
            return dict(rows[0])
        if kind == "db_delete":
            by_id_values = self._evaluate_expr_dict(params.get("by_id"), evaluator, step_name, "by id")
            if not record.primary_key or record.primary_key not in by_id_values:
                raise Namel3ssError(
                    f"Step '{step_name}' must include primary key '{record.primary_key}' inside 'by id'."
                )
            pk_field = record.fields.get(record.primary_key)
            filters = {
                record.primary_key: self._coerce_record_value(
                    record.name,
                    pk_field,
                    by_id_values[record.primary_key],
                    step_name,
                )
            }
            deleted = frames.delete(frame_name, filters)
            return {"ok": deleted > 0, "deleted": deleted}
        raise Namel3ssError(f"Unsupported record operation '{kind}'.")

    def _execute_auth_step(
        self,
        kind: str,
        auth_config: Any,
        record: Any,
        params: dict[str, Any],
        evaluator: ExpressionEvaluator,
        runtime_ctx: FlowRuntimeContext,
        step_name: str,
        state: FlowState,
    ) -> Any:
        frames = runtime_ctx.frames
        if frames is None:
            raise Namel3ssError("Frame registry unavailable for auth operations.")
        frame_name = getattr(record, "frame", None)
        if not frame_name:
            raise Namel3ssError("Auth user_record is missing an associated frame.")
        identifier_field = getattr(auth_config, "identifier_field", None)
        password_hash_field = getattr(auth_config, "password_hash_field", None)
        id_field = getattr(auth_config, "id_field", None) or getattr(record, "primary_key", None)
        if not identifier_field or not password_hash_field:
            raise Namel3ssError("Auth configuration is incomplete.")
        identifier_field_obj = record.fields.get(identifier_field)
        if not identifier_field_obj:
            raise Namel3ssError(f"Auth identifier_field '{identifier_field}' not found on user_record.")
        user_ctx = getattr(runtime_ctx, "user_context", None)
        if user_ctx is None:
            user_ctx = {"id": None, "is_authenticated": False, "record": None}
            runtime_ctx.user_context = user_ctx
        if "user" not in state.context or state.context.get("user") is None:
            state.context["user"] = user_ctx
        input_values = self._evaluate_expr_dict(params.get("input"), evaluator, step_name, "input")
        identifier_value = input_values.get(identifier_field)
        password_value = input_values.get("password")
        if kind == "auth_register":
            if identifier_value is None or password_value is None:
                raise Namel3ssError("Missing identifier or password for auth_register.")
            filters = {
                identifier_field: self._coerce_record_value(record.name, identifier_field_obj, identifier_value, step_name)
            }
            existing = frames.query(frame_name, filters)
            if existing:
                return {"ok": False, "code": "AUTH_USER_EXISTS", "error": "User already exists."}
            password_hash = hash_password(str(password_value))
            values: dict[str, Any] = {}
            for key, raw_val in input_values.items():
                if key == "password":
                    continue
                if key == password_hash_field:
                    continue
                values[key] = raw_val
            values[identifier_field] = identifier_value
            values[password_hash_field] = password_hash
            if id_field and id_field not in values:
                pk_field = record.fields.get(id_field)
                if pk_field and getattr(pk_field, "type", None) == "uuid":
                    values[id_field] = str(uuid4())
            normalized = self._prepare_record_values(
                record,
                values,
                step_name,
                include_defaults=True,
                enforce_required=True,
            )
            frames.insert(frame_name, normalized)
            return {"ok": True, "user_id": normalized.get(id_field), "user": dict(normalized)}
        if kind == "auth_login":
            if identifier_value is None or password_value is None:
                raise Namel3ssError("Missing identifier or password for auth_login.")
            filters = {
                identifier_field: self._coerce_record_value(record.name, identifier_field_obj, identifier_value, step_name)
            }
            rows = frames.query(frame_name, filters)
            if not rows:
                return {"ok": False, "code": "AUTH_INVALID_CREDENTIALS", "error": "Invalid credentials."}
            user_row = rows[0]
            stored_hash = user_row.get(password_hash_field)
            valid = False
            try:
                valid = verify_password(str(password_value), str(stored_hash or ""))
            except Namel3ssError as exc:
                raise Namel3ssError(str(exc))
            if not valid:
                return {"ok": False, "code": "AUTH_INVALID_CREDENTIALS", "error": "Invalid credentials."}
            user_id = user_row.get(id_field)
            user_ctx["id"] = user_id
            user_ctx["record"] = dict(user_row)
            user_ctx["is_authenticated"] = True
            if runtime_ctx.execution_context:
                runtime_ctx.execution_context.user_context = user_ctx
                if getattr(runtime_ctx.execution_context, "metadata", None) is not None:
                    runtime_ctx.execution_context.metadata["user_id"] = user_id
            return {"ok": True, "user_id": user_id, "user": dict(user_row)}
        if kind == "auth_logout":
            user_ctx["id"] = None
            user_ctx["record"] = None
            user_ctx["is_authenticated"] = False
            if runtime_ctx.execution_context and getattr(runtime_ctx.execution_context, "metadata", None) is not None:
                runtime_ctx.execution_context.metadata.pop("user_id", None)
                runtime_ctx.execution_context.user_context = user_ctx
            return {"ok": True}
        raise Namel3ssError(f"Unsupported auth operation '{kind}'.")
    def _eval_rulegroup(self, expr: ast_nodes.RuleGroupRefExpr, state: FlowState, runtime_ctx: FlowRuntimeContext) -> tuple[bool, Any]:
        groups = getattr(runtime_ctx.program, "rulegroups", {}) if runtime_ctx else {}
        rules = groups.get(expr.group_name) or {}
        tracer = runtime_ctx.tracer if runtime_ctx else None
        if expr.condition_name:
            rule_expr = rules.get(expr.condition_name)
            if rule_expr is None:
                return False, None
            result = bool(self._eval_expr(rule_expr, state, runtime_ctx))
            if tracer:
                tracer.record_flow_event(
                    "condition.rulegroup.eval",
                    {
                        "rulegroup": expr.group_name,
                        "condition": expr.condition_name,
                        "result": result,
                        "evaluated": result,
                        "taken": result,
                    },
                )
            return result, result
        results_map: dict[str, bool] = {}
        all_true = True
        for name, rule_expr in rules.items():
            val = bool(self._eval_expr(rule_expr, state, runtime_ctx))
            results_map[name] = val
            if not val:
                all_true = False
        if tracer:
            tracer.record_flow_event(
                "condition.rulegroup.eval",
                {
                    "rulegroup": expr.group_name,
                    "mode": "all",
                    "results": results_map,
                    "evaluated": all_true,
                    "taken": all_true,
                },
            )
        return all_true, all_true

    def _eval_expr(self, expr: ast_nodes.Expr, state: FlowState, runtime_ctx: FlowRuntimeContext | None = None) -> Any:
        if isinstance(expr, ast_nodes.PatternExpr):
            match, _ = self._match_pattern(expr, state, runtime_ctx) if runtime_ctx else (False, None)
            return match
        evaluator = self._build_evaluator(state, runtime_ctx)
        try:
            return evaluator.evaluate(expr)
        except EvaluationError as exc:
            raise Namel3ssError(str(exc))

    def _match_pattern(self, pattern: ast_nodes.PatternExpr, state: FlowState, runtime_ctx: FlowRuntimeContext) -> tuple[bool, Any]:
        found, subject = self._resolve_identifier(pattern.subject.name, state, runtime_ctx)
        if not found or not isinstance(subject, dict):
            return False, None
        for pair in pattern.pairs:
            subject_val = subject.get(pair.key)
            val_expr = pair.value
            if isinstance(val_expr, ast_nodes.BinaryOp) and isinstance(val_expr.left, ast_nodes.Identifier):
                left_val = subject_val if val_expr.left.name == pair.key else self._eval_expr(val_expr.left, state, runtime_ctx)
                right_val = self._eval_expr(val_expr.right, state, runtime_ctx) if val_expr.right else None
                op = val_expr.op
                try:
                    if op == "and":
                        if not (bool(left_val) and bool(right_val)):
                            return False, None
                    elif op == "or":
                        if not (bool(left_val) or bool(right_val)):
                            return False, None
                    elif op in {"is", "==", "="}:
                        if left_val != right_val:
                            return False, None
                    elif op in {"is not", "!="}:
                        if left_val == right_val:
                            return False, None
                    elif op == "<":
                        if not (left_val < right_val):
                            return False, None
                    elif op == ">":
                        if not (left_val > right_val):
                            return False, None
                    elif op == "<=":
                        if not (left_val <= right_val):
                            return False, None
                    elif op == ">=":
                        if not (left_val >= right_val):
                            return False, None
                except Exception:
                    return False, None
                continue
            expected = self._eval_expr(val_expr, state, runtime_ctx)
            if subject_val != expected:
                return False, None
        return True, subject

    def _pattern_to_repr(self, pattern: ast_nodes.PatternExpr) -> dict:
        return {pair.key: self._expr_to_str(pair.value) for pair in pattern.pairs}

    def _eval_condition_with_binding(self, expr: ast_nodes.Expr | None, state: FlowState, runtime_ctx: FlowRuntimeContext) -> tuple[bool, Any]:
        if expr is None:
            return True, None
        if isinstance(expr, ast_nodes.PatternExpr):
            match, subject_val = self._match_pattern(expr, state, runtime_ctx)
            return match, subject_val
        if isinstance(expr, ast_nodes.RuleGroupRefExpr):
            res, val = self._eval_rulegroup(expr, state, runtime_ctx)
            return res, val
        evaluator = self._build_evaluator(state, runtime_ctx)
        try:
            value = evaluator.evaluate(expr)
        except EvaluationError as exc:
            raise Namel3ssError(str(exc))
        if not isinstance(value, bool):
            raise Namel3ssError("Condition must evaluate to a boolean")
        return bool(value), value

    async def _run_condition_node(self, node: FlowNode, state: FlowState, runtime_ctx: FlowRuntimeContext) -> dict:
        tracer = runtime_ctx.tracer
        branches = node.config.get("branches") or []
        selected = None
        selected_label = None
        binding_value = None
        binding_name = None
        env = state.variables or runtime_ctx.variables or VariableEnvironment()
        for idx, br in enumerate(branches):
            condition_expr = getattr(br, "condition", None)
            is_pattern = isinstance(condition_expr, ast_nodes.PatternExpr)
            if is_pattern:
                result, candidate_binding = self._eval_condition_with_binding(condition_expr, state, runtime_ctx)
            else:
                result, candidate_binding = self._eval_condition_with_binding(condition_expr, state, runtime_ctx)
            expr_display = self._expr_to_str(condition_expr)
            if getattr(br, "label", None) == "unless":
                result = not result
                expr_display = f"unless {expr_display}"
            if tracer:
                payload = {
                    "node_id": node.id,
                    "condition": expr_display,
                    "result": result,
                    "branch_index": idx,
                }
                if getattr(br, "macro_origin", None):
                    payload["macro"] = getattr(br, "macro_origin", None)
                if result and getattr(br, "binding", None):
                    payload["binding"] = {"name": getattr(br, "binding", None), "value": candidate_binding}
                if is_pattern and isinstance(condition_expr, ast_nodes.PatternExpr):
                    payload.update(
                        {
                            "subject": condition_expr.subject.name,
                            "pattern": self._pattern_to_repr(condition_expr),
                        }
                    )
                    tracer.record_flow_event("condition.pattern.eval", payload)
                else:
                    tracer.record_flow_event("flow.condition.eval", payload)
            if result:
                selected = br
                selected_label = br.label or f"branch-{idx}"
                binding_name = getattr(br, "binding", None)
                binding_value = candidate_binding
                break
        if selected is None:
            return {"condition": "no-branch"}

        # apply binding locally for the chosen branch
        previous_binding = None
        had_prev = False
        if binding_name:
            if env.has(binding_name):
                had_prev = True
                previous_binding = env.resolve(binding_name)
                env.assign(binding_name, binding_value)
            else:
                env.declare(binding_name, binding_value)
            state.set(binding_name, binding_value)

        for action in selected.actions:
            if isinstance(action, IRAction):
                cfg = {
                    "kind": action.kind,
                    "target": action.target,
                    "step_name": f"{node.id}.{action.target}",
                    "reason": "conditional",
                    "params": action.args or {},
                }
                if action.message:
                    cfg["params"] = {"message": action.message}
                await self._run_inline_sequence(node.id, [cfg], state, runtime_ctx)
            else:
                await self._execute_statement(action, state, runtime_ctx, node.id)
        if binding_name:
            if had_prev:
                env.assign(binding_name, previous_binding)
                state.set(binding_name, previous_binding)
            else:
                env.remove(binding_name)
                state.data.pop(binding_name, None)
        return {"condition": selected_label}


class TimedStepError(Exception):
    def __init__(self, original: Exception, duration: float) -> None:
        message = str(original) or "timeout"
        super().__init__(message)
        self.original = original
        self.duration = duration
