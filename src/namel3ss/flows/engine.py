"""
Flow execution engine V3: graph-based runtime with branching, parallelism, and
error boundaries.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import numbers
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from .. import ast_nodes
from ..agent.engine import AgentRunner
from ..ai.registry import ModelRegistry
from ..ai.router import ModelRouter
from ..errors import (
    Namel3ssError,
    ProviderAuthError,
    ProviderCircuitOpenError,
    ProviderConfigError,
    ProviderRetryError,
    ProviderTimeoutError,
)
from ..runtime.auth import hash_password, verify_password
from ..ir import (
    IRAction,
    IRBulkCreateSpec,
    IRBulkDeleteSpec,
    IRBulkUpdateSpec,
    IRAskUser,
    IRCheckpoint,
    IRFlow,
    IRFlowLoop,
    IRFlowStep,
    IRTransactionBlock,
    IRForEach,
    IRForm,
    IRIf,
    IRLet,
    IRLog,
    IRMatch,
    IRMatchBranch,
    IRNote,
    IRProgram,
    IRRecordQuery,
    IRRecordOrderBy,
    IRConditionLeaf,
    IRConditionAnd,
    IRConditionOr,
    IRConditionAllGroup,
    IRConditionAnyGroup,
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
    get_user_context,
    _apply_conversation_summary_if_needed,
    _build_vector_context_messages,
    _upsert_vector_memory,
    get_vector_memory_settings,
)
from ..runtime.retries import get_default_retry_config, with_retries_and_timeout
from ..runtime.circuit_breaker import default_circuit_breaker
from ..runtime.eventlog import EventLogger
from ..runtime.expressions import (
    EvaluationError,
    ExpressionEvaluator,
    VariableEnvironment,
    build_missing_field_error,
)
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
        max_parallel_tasks: int | None = None,
        global_stream_callback: Any = None,
    ) -> None:
        self.program = program
        self.model_registry = model_registry
        self.tool_registry = tool_registry
        self.agent_runner = agent_runner
        self.router = router
        self.metrics = metrics
        self.secrets = secrets
        from ..runtime.config import get_max_parallel_tasks

        self.max_parallel_tasks = max_parallel_tasks if max_parallel_tasks is not None else get_max_parallel_tasks()
        self.global_stream_callback = global_stream_callback
        self.frame_registry = FrameRegistry(program.frames if program else {})
        self.vector_registry = VectorStoreRegistry(program, secrets=secrets) if program else None
        self.retry_config = get_default_retry_config()
        self.retry_error_types = (
            ProviderTimeoutError,
            urllib.error.URLError,
            ConnectionError,
            TimeoutError,
        )
        self.circuit_breaker = default_circuit_breaker
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

    def _resolve_step_kind(self, node: FlowNode) -> str:
        cfg = node.config if isinstance(node.config, dict) else {}
        kind = node.kind or ""
        statements = cfg.get("statements") or []
        if not kind:
            if statements:
                return "script"
            return "script"
        builtin = {"script", "ai", "agent", "tool"}
        supported = builtin | {
            "condition",
            "branch",
            "join",
            "parallel",
            "for_each",
            "try",
            "goto_flow",
            "subflow",
            "rag",
            "vector",
            "vector_query",
            "vector_index_frame",
            "rag_query",
            "frame_insert",
            "frame_query",
            "frame_update",
             "frame_delete",
             "db_create",
             "db_update",
             "db_delete",
             "db_bulk_create",
             "db_bulk_update",
             "db_bulk_delete",
             "find",
             "auth_register",
             "auth_login",
             "auth_logout",
             "noop",
            "function",
            "transaction",
        }
        if kind in supported:
            return "script" if kind == "function" and statements else kind
        raise Namel3ssError(
            f'I don\'t know how to run a step with kind is "{kind}".\nSupported built-in kinds are "script", "ai", "agent", and "tool".'
        )

    def _apply_destructuring(self, pattern, value, env, state, *, is_constant: bool = False) -> None:
        if pattern.kind == "record":
            if not isinstance(value, dict):
                raise Namel3ssError("N3-3300: I can only destructure fields from a record value.")
            for field in pattern.fields:
                target_name = field.alias or field.name
                if field.name not in value:
                    raise Namel3ssError(
                        build_missing_field_error(
                            field.name,
                            value,
                            context=f"I can't destructure field {field.name} from this record.",
                        )
                    )
                env.declare(target_name, value.get(field.name), is_constant=is_constant)
                state.set(target_name, value.get(field.name))
            return
        if pattern.kind == "list":
            if not isinstance(value, (list, tuple)):
                raise Namel3ssError("Cannot destructure list; expected a list/sequence.")
            fields = pattern.fields
            if len(value) < len(fields):
                raise Namel3ssError(
                    f"Cannot destructure list into [{', '.join(fields)}]; it has only {len(value)} elements."
                )
            for idx, name in enumerate(fields):
                env.declare(name, value[idx] if idx < len(value) else None, is_constant=is_constant)
                state.set(name, value[idx] if idx < len(value) else None)
            return
        raise Namel3ssError("Unsupported destructuring pattern.")

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
        user_context = get_user_context(getattr(context, "user_context", None))
        if getattr(context, "metadata", None) is not None and user_context.get("id") and "user_id" not in context.metadata:
            context.metadata["user_id"] = user_context.get("id")
        try:
            context.vectorstores = self.vector_registry
        except Exception:
            pass
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
            rag_pipelines=getattr(self.program, "rag_pipelines", {}),
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
            provider_cache=context.provider_cache or None,
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
        runtime_ctx.step_aliases = self._collect_step_aliases(flow.steps)
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
            resolved_kind = self._resolve_step_kind(node)
            target_label = node.config.get("target") if isinstance(node.config, dict) else None
            target_label = target_label or node.id
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
        self, node: FlowNode, state: FlowState, runtime_ctx: FlowRuntimeContext, resolved_kind: str | None = None
    ) -> Optional[FlowStepResult]:
        tracer = runtime_ctx.tracer
        resolved_kind = resolved_kind or self._resolve_step_kind(node)
        target = node.config.get("target")
        target_label = target or node.id
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
            f"flow.step.{resolved_kind}", attributes={"step": step_name, "flow_target": target_label, "kind": resolved_kind}
        ):
            if resolved_kind == "noop":
                output = node.config.get("output")
            elif resolved_kind == "ai":
                if not target:
                    raise Namel3ssError("This AI step needs a target (the model to call), but none was provided.")
                if target not in runtime_ctx.program.ai_calls:
                    raise Namel3ssError(f'I couldn\'t find an AI call named "{target}". Check your configuration or plugin setup.')
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
                    output = await self._call_ai_step(
                        ai_call=ai_call,
                        base_context=base_context,
                        runtime_ctx=runtime_ctx,
                        step_name=step_name,
                        flow_name=state.context.get("flow_name") or "",
                        tools_mode=tools_mode,
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
            elif resolved_kind == "agent":
                if not target:
                    raise Namel3ssError("This agent step needs a target (the agent to run), but none was provided.")
                if target not in runtime_ctx.program.agents:
                    raise Namel3ssError(f'I couldn\'t find an agent named "{target}". Check your configuration or plugin setup.')
                raw_output = await asyncio.to_thread(runtime_ctx.agent_runner.run, target, base_context)
                output = asdict(raw_output) if is_dataclass(raw_output) else raw_output
            elif resolved_kind == "tool":
                if not target:
                    raise Namel3ssError("This tool step needs a target (the tool name), but none was provided.")
                tool_cfg = runtime_ctx.tool_registry.get(target)
                if not tool_cfg:
                    raise Namel3ssError(f'I couldn\'t find a tool named "{target}". Check your configuration or plugin setup.')
                output = await self._execute_tool_call(node, state, runtime_ctx, tool_override=tool_cfg)
            elif resolved_kind in {"frame_insert", "frame_query", "frame_update", "frame_delete"}:
                params = node.config.get("params") or {}
                frame_name = params.get("frame") or target
                if not frame_name:
                    raise Namel3ssError(
                        "N3L-831: frame_insert/frame_query/frame_update/frame_delete requires a frame name."
                    )
                evaluator = self._build_evaluator(state, runtime_ctx)
                operation = resolved_kind.replace("frame_", "")
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
                if resolved_kind == "frame_insert":
                    values_expr = params.get("values") or {}
                    if not isinstance(values_expr, dict) or not values_expr:
                        raise Namel3ssError("N3L-832: frame_insert requires non-empty values.")
                    row: dict[str, Any] = {}
                    for k, v in values_expr.items():
                        row[k] = evaluator.evaluate(v) if isinstance(v, ast_nodes.Expr) else v
                    runtime_ctx.frames.insert(frame_name, row)
                    output = row
                elif resolved_kind == "frame_query":
                    filters_expr = params.get("where") or {}
                    filters = self._evaluate_where_conditions(filters_expr, evaluator, step_name, record=None)
                    output = runtime_ctx.frames.query(frame_name, filters)
                elif resolved_kind == "frame_update":
                    set_expr = params.get("set") or {}
                    if not isinstance(set_expr, dict) or not set_expr:
                        raise Namel3ssError("N3L-840: frame_update step must define a non-empty 'set' block.")
                    filters_expr = params.get("where") or {}
                    filters = self._evaluate_where_conditions(filters_expr, evaluator, step_name, record=None)
                    updates: dict[str, Any] = {}
                    for k, v in set_expr.items():
                        updates[k] = evaluator.evaluate(v) if isinstance(v, ast_nodes.Expr) else v
                    output = runtime_ctx.frames.update(frame_name, filters, updates)
                else:  # frame_delete
                    filters_expr = params.get("where") or {}
                    if not filters_expr:
                        raise Namel3ssError("N3L-841: frame_delete step requires a 'where' block to avoid deleting all rows.")
                    filters = self._evaluate_where_conditions(filters_expr, evaluator, step_name, record=None)
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
                        if resolved_kind in {"frame_query", "frame_update", "frame_delete"}:
                            payload["row_count"] = output if isinstance(output, (int, float)) else (len(output) if isinstance(output, list) else None)
                        runtime_ctx.event_logger.log(payload)
                    except Exception:
                        pass
            elif resolved_kind in {"db_create", "db_update", "db_delete", "db_bulk_create", "db_bulk_update", "db_bulk_delete", "find"}:
                params = node.config.get("params") or {}
                record_name = target or target_label
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
                    kind=resolved_kind,
                    record=record,
                    params=params,
                    evaluator=evaluator,
                    runtime_ctx=runtime_ctx,
                    step_name=step_name,
                )
            elif resolved_kind in {"auth_register", "auth_login", "auth_logout"}:
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
                    kind=resolved_kind,
                    auth_config=auth_cfg,
                    record=record,
                    params=params,
                    evaluator=evaluator,
                    runtime_ctx=runtime_ctx,
                    step_name=step_name,
                    state=state,
                )
            elif resolved_kind == "vector_index_frame":
                params = node.config.get("params") or {}
                vector_store_name = params.get("vector_store") or target
                if not vector_store_name:
                    raise Namel3ssError(
                        f"Step '{step_name}' must specify a 'vector_store'. Add 'vector_store is \"kb\"' to the step."
                    )
                if not runtime_ctx.vectorstores:
                    raise Namel3ssError("Vector store registry unavailable.")
                evaluator = self._build_evaluator(state, runtime_ctx)
                cfg = runtime_ctx.vectorstores.get(vector_store_name)
                filters_expr = params.get("where")
                use_expr = filters_expr is not None and not isinstance(filters_expr, (dict, list))
                filters = None if use_expr else self._evaluate_where_conditions(filters_expr or {}, evaluator, step_name, record=None)
                base_rows = runtime_ctx.frames.query(cfg.frame, filters) if not use_expr else runtime_ctx.frames.query(cfg.frame)
                rows: list[dict] = []
                if use_expr:
                    for row in base_rows:
                        if not isinstance(row, dict):
                            continue
                        row_env = VariableEnvironment({"row": row, **dict(row)})
                        row_evaluator = ExpressionEvaluator(
                            row_env,
                            resolver=lambda name, r=row: (True, r)
                            if name == "row"
                            else ((True, r.get(name)) if isinstance(r, dict) and name in r else evaluator.resolver(name)),
                        )
                        try:
                            keep = row_evaluator.evaluate(filters_expr)
                        except EvaluationError as exc:
                            raise Namel3ssError(str(exc)) from exc
                        if not isinstance(keep, bool):
                            raise Namel3ssError(
                                f"N3F-1003: The 'where' clause on frame '{cfg.frame}' must be a boolean expression."
                            )
                        if keep:
                            rows.append(row)
                else:
                    rows = base_rows
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
                    ids: list[str] = []
                    texts: list[str] = []
                    metadata: list[dict] = []
                    metadata_cols = getattr(cfg, "metadata_columns", []) or []
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
                            if metadata_cols:
                                meta_entry: dict[str, object] = {}
                                for col in metadata_cols:
                                    meta_entry[col] = row.get(col)
                                metadata.append(meta_entry)
                    runtime_ctx.vectorstores.index_texts(
                        vector_store_name,
                        ids,
                        texts,
                        metadata if metadata_cols else None,
                    )
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
            elif resolved_kind == "vector_query":
                params = node.config.get("params") or {}
                vector_store_name = params.get("vector_store") or target
                if not vector_store_name:
                    raise Namel3ssError(
                        f"Step '{step_name}' must specify a 'vector_store'. Add 'vector_store is \"kb\"' to the step."
                    )
                if not runtime_ctx.vectorstores:
                    raise Namel3ssError("Vector store registry unavailable.")
                evaluator = self._build_evaluator(state, runtime_ctx)
                cfg = runtime_ctx.vectorstores.get(vector_store_name)
                query_expr = params.get("query_text")
                if query_expr is None:
                    raise Namel3ssError(
                        f"Step '{step_name}' must define 'query_text'. Add 'query_text is ...' inside the step."
                    )
                query_text = evaluator.evaluate(query_expr) if isinstance(query_expr, ast_nodes.Expr) else query_expr
                if not isinstance(query_text, str):
                    raise Namel3ssError(
                        f"The 'query_text' for step '{step_name}' must be a string value."
                    )
                top_k_expr = params.get("top_k")
                top_k_val = 5
                if top_k_expr is not None:
                    top_k_val = evaluator.evaluate(top_k_expr) if isinstance(top_k_expr, ast_nodes.Expr) else top_k_expr
                try:
                    top_k_int = int(top_k_val)
                except Exception:
                    raise Namel3ssError(
                        f"Top_k for step '{step_name}' must be a positive integer (for example, 3, 5, or 10)."
                    )
                if top_k_int < 1:
                    raise Namel3ssError(
                        f"Top_k for step '{step_name}' must be a positive integer (for example, 3, 5, or 10)."
                    )
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
            elif resolved_kind == "rag_query":
                params = node.config.get("params") or {}
                pipeline_name = params.get("pipeline")
                question_expr = params.get("question")
                if not pipeline_name:
                    raise Namel3ssError(
                        f"Step '{step_name}' refers to a RAG pipeline, but no pipeline is specified. Add 'pipeline is \"...\"'."
                    )
                evaluator = self._build_evaluator(state, runtime_ctx)
                question_val = evaluator.evaluate(question_expr) if isinstance(question_expr, ast_nodes.Expr) else question_expr
                if not isinstance(question_val, str):
                    raise Namel3ssError(
                        f"The 'question' expression for step '{step_name}' must evaluate to a string."
                    )
                output = await self._run_rag_pipeline(
                    pipeline_name,
                    question_val,
                    state,
                    runtime_ctx,
                    base_context,
                    flow_name=state.context.get("flow_name") or "",
                    step_name=step_name,
                )
            elif resolved_kind == "rag":
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
            elif resolved_kind == "branch":
                output = {"branch": True}
            elif resolved_kind == "join":
                output = {"join": True}
            elif resolved_kind == "subflow":
                subflow = runtime_ctx.program.flows.get(target)
                if not subflow:
                    raise Namel3ssError(f"Subflow '{target}' not found")
                graph = flow_ir_to_graph(subflow)
                sub_state = state.copy()
                result = await self.a_run_flow(graph, sub_state, runtime_ctx, flow_name=target)
                output = {"subflow": target, "state": result.state.data if result.state else {}}
            elif resolved_kind == "script":
                statements = node.config.get("statements") or []
                output = await self._execute_script(statements, state, runtime_ctx, node.id)
            elif resolved_kind == "condition":
                output = await self._run_condition_node(node, state, runtime_ctx)
            elif resolved_kind == "function":
                func = node.config.get("callable")
                if not callable(func):
                    raise Namel3ssError(f"Function node '{node.id}' missing callable")
                output = func(state)
            elif resolved_kind == "parallel":
                output = await self._execute_parallel_block(node, state, runtime_ctx)
            elif resolved_kind == "transaction":
                output = await self._execute_transaction_block(node, state, runtime_ctx)
            elif resolved_kind == "for_each":
                output = await self._execute_for_each(node, state, runtime_ctx)
            elif resolved_kind == "try":
                output = await self._execute_try_catch(node, state, runtime_ctx)
            elif resolved_kind == "goto_flow":
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
                raise Namel3ssError(f"Unsupported flow step kind '{resolved_kind}'")

        state.set(f"step.{node.id}.output", output)
        state.set("last_output", output)
        if tracer:
            tracer.record_flow_step(
                step_name=step_name,
                kind=resolved_kind,
                target=target_label,
                success=True,
                output_preview=str(output)[:200] if output is not None else None,
                node_id=node.id,
        )
        return FlowStepResult(
            step_name=step_name,
            kind=resolved_kind,
            target=target_label,
            success=True,
            output=output,
            node_id=node.id,
            redirect_to=state.context.get("__redirect_flow__"),
        )

    async def _call_ai_step(
        self,
        ai_call,
        base_context: ExecutionContext,
        runtime_ctx: FlowRuntimeContext,
        step_name: str,
        flow_name: str,
        tools_mode: str | None = None,
    ) -> Any:
        provider, provider_model, provider_name = runtime_ctx.model_registry.resolve_provider_for_ai(ai_call)
        provider_model = provider_model or ai_call.model_name or provider_name
        provider_key = f"model:{provider_name}:{provider_model}"
        start_time = time.monotonic()
        retries = 0
        last_error_type: str | None = None
        tracer_instance = runtime_ctx.tracer or default_tracer
        event_logger = runtime_ctx.event_logger
        if event_logger:
            try:
                event_logger.log(
                    {
                        "kind": "provider",
                        "event_type": "provider_call_start",
                        "flow_name": flow_name,
                        "step_name": step_name,
                        "provider": provider_name,
                        "model": provider_model,
                        "status": "running",
                    }
                )
            except Exception:
                pass

        def _on_error(exc: BaseException, attempt: int) -> None:
            nonlocal retries, last_error_type
            retries = max(retries, attempt + 1)
            last_error_type = exc.__class__.__name__

        async def _invoke() -> Any:
            return await asyncio.to_thread(
                execute_ai_call_with_registry,
                ai_call,
                runtime_ctx.model_registry,
                runtime_ctx.router,
                base_context,
                tools_mode,
            )

        status = "success"
        with tracer_instance.span(
            "provider.call",
            attributes={
                "provider": provider_name,
                "model": provider_model,
                "flow": flow_name,
                "step": step_name,
            },
        ):
            try:
                return await with_retries_and_timeout(
                    _invoke,
                    config=self.retry_config,
                    error_types=self.retry_error_types,
                    on_error=_on_error,
                    circuit_breaker=self.circuit_breaker,
                    provider_key=provider_key,
                )
            except ProviderCircuitOpenError as exc:
                status = "circuit_open"
                last_error_type = exc.__class__.__name__
                raise
            except ProviderTimeoutError as exc:
                status = "timeout"
                last_error_type = exc.__class__.__name__
                raise
            except ProviderRetryError as exc:
                status = "failure"
                last_error_type = exc.__class__.__name__
                raise
            except Exception as exc:
                status = "failure"
                last_error_type = exc.__class__.__name__
                raise
            finally:
                duration = time.monotonic() - start_time
                try:
                    default_metrics.record_provider_call(provider_name, provider_model, status, duration)
                    if status == "circuit_open":
                        default_metrics.record_circuit_open(provider_name)
                except Exception:
                    pass
                if event_logger:
                    try:
                        event_logger.log(
                            {
                                "kind": "provider",
                                "event_type": "provider_call_end",
                                "flow_name": flow_name,
                                "step_name": step_name,
                                "provider": provider_name,
                                "model": provider_model,
                                "status": status,
                                "duration": duration,
                                "retries": retries,
                                "error_type": last_error_type,
                            }
                        )
                    except Exception:
                        pass

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
        provider_key = f"model:{provider_name}:{provider_model}"
        tracer_instance = runtime_ctx.tracer or default_tracer
        event_logger = runtime_ctx.event_logger
        status = "success"
        last_error_type: str | None = None
        start_time = time.monotonic()
        vector_enabled, vector_store_name, vector_top_k = get_vector_memory_settings()
        vector_registry = getattr(base_context, "vectorstores", None)
        if event_logger:
            try:
                event_logger.log(
                    {
                        "kind": "provider",
                        "event_type": "provider_call_start",
                        "flow_name": flow_name,
                        "step_name": step_name,
                        "provider": provider_name,
                        "model": provider_model,
                        "status": "running",
                        "streaming": True,
                    }
                )
            except Exception:
                pass
        if self.circuit_breaker and not self.circuit_breaker.should_allow_call(provider_key):
            status = "circuit_open"
            last_error_type = "ProviderCircuitOpenError"
            duration = time.monotonic() - start_time
            try:
                default_metrics.record_provider_call(provider_name, provider_model, status, duration)
                default_metrics.record_circuit_open(provider_name)
            except Exception:
                pass
            if event_logger:
                try:
                    event_logger.log(
                        {
                            "kind": "provider",
                            "event_type": "provider_call_end",
                            "flow_name": flow_name,
                            "step_name": step_name,
                            "provider": provider_name,
                            "model": provider_model,
                            "status": status,
                            "duration": duration,
                            "retries": 0,
                            "error_type": last_error_type,
                            "streaming": True,
                        }
                    )
                except Exception:
                    pass
            raise ProviderCircuitOpenError(f"Circuit open for provider '{provider_key}'.")
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
        vector_context_messages: list[dict[str, str]] = []
        if vector_enabled:
            if not vector_registry:
                raise ProviderConfigError("Vector memory is enabled but no vector store registry is configured.")
            try:
                vector_context_messages = _build_vector_context_messages(
                    vector_registry,
                    user_content,
                    vector_store_name,
                    vector_top_k,
                )
            except Exception as exc:
                raise ProviderConfigError(
                    f"Vector memory store '{vector_store_name}' is unavailable or misconfigured: {exc}"
                ) from exc
        if vector_context_messages:
            messages.extend(vector_context_messages)
        user_message = {"role": "user", "content": user_content}
        messages.append(user_message)
        messages = _apply_conversation_summary_if_needed(messages, provider, provider_model, provider_name)

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

        with tracer_instance.span(
            "provider.call",
            attributes={
                "provider": provider_name,
                "model": provider_model,
                "flow": flow_name,
                "step": step_name,
                "streaming": True,
            },
        ):
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
                if self.circuit_breaker:
                    self.circuit_breaker.record_success(provider_key)
                if mode == "sentences":
                    sentence_buffer = await _flush_sentence_chunks(sentence_buffer, force=True)
                await emit("done", full=full_text)
            except urllib.error.HTTPError as exc:
                status = "failure"
                last_error_type = exc.__class__.__name__
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(provider_key, exc)
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
                status = "failure"
                last_error_type = exc.__class__.__name__
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(provider_key, exc)
                await emit("error", error=str(exc), code=exc.code)
                raise
            except Exception as exc:
                status = "failure"
                last_error_type = exc.__class__.__name__
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(provider_key, exc)
                await emit("error", error=str(exc), code=getattr(exc, "code", None))
                raise
            finally:
                duration = time.monotonic() - start_time
                try:
                    default_metrics.record_provider_call(provider_name, provider_model, status, duration)
                    if status == "circuit_open":
                        default_metrics.record_circuit_open(provider_name)
                except Exception:
                    pass
                if event_logger:
                    try:
                        event_logger.log(
                            {
                                "kind": "provider",
                                "event_type": "provider_call_end",
                                "flow_name": flow_name,
                                "step_name": step_name,
                                "provider": provider_name,
                                "model": provider_model,
                                "status": status,
                                "duration": duration,
                                "retries": 0,
                                "error_type": last_error_type,
                                "streaming": True,
                            }
                        )
                    except Exception:
                        pass

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
        if vector_enabled:
            if not vector_registry:
                raise ProviderConfigError("Vector memory is enabled but no vector store registry is configured.")
            try:
                _upsert_vector_memory(
                    vector_registry,
                    vector_store_name,
                    [user_message, {"role": "assistant", "content": full_text}],
                    metadata={"session_id": session_id, "ai": ai_call.name, "user_id": user_id},
                )
            except Exception as exc:
                raise ProviderConfigError(
                    f"Vector memory store '{vector_store_name}' is unavailable or misconfigured: {exc}"
                ) from exc
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

    async def _execute_transaction_block(self, node: FlowNode, state: FlowState, runtime_ctx: FlowRuntimeContext):
        frames = runtime_ctx.frames
        if frames is None:
            raise Namel3ssError("Frame registry unavailable for transactions.")
        stack = runtime_ctx.transaction_stack
        if stack is None:
            stack = []
            runtime_ctx.transaction_stack = stack
        if stack:
            raise Namel3ssError(
                "Nested transactions are not supported yet. Remove the inner transaction: block or move its steps outside."
            )
        snapshot = frames.snapshot()
        stack.append(snapshot)
        flow_name = state.context.get("flow_name") or (
            runtime_ctx.execution_context.flow_name if runtime_ctx.execution_context else None
        )
        flow_label = f'flow "{flow_name}"' if flow_name else "this flow"
        body = node.config.get("body") or []
        step_id = node.config.get("step_name", node.id)
        try:
            await self._run_inline_sequence(step_id, body, state, runtime_ctx)
        except Exception as exc:
            frames.restore(stack.pop())
            message = (
                f"This transaction in {flow_label} failed and all record changes were rolled back.\n"
                f"Reason: {exc}"
            )
            wrapped = Namel3ssError(message)
            if hasattr(exc, "diagnostics"):
                wrapped.diagnostics = getattr(exc, "diagnostics")
            raise wrapped from exc
        stack.pop()
        return {"transaction": "committed", "steps": len(body)}

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
            items = self._require_list_iterable(iterable_value, context="This for each loop")
        elif items_path:
            iterable_value = state.get(items_path, []) or []
            items = self._require_list_iterable(iterable_value, context="This for each loop")
        elif items_val is not None:
            items = self._require_list_iterable(items_val, context="This for each loop")
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
                if state.context.get("__redirect_flow__") or state.context.get("__awaiting_input__"):
                    break
        finally:
            if var_name:
                if had_prev:
                    env.assign(var_name, prev_val)
                    state.set(var_name, prev_val)
                else:
                    env.remove(var_name)
                    if hasattr(env, "mark_loop_var_exited"):
                        env.mark_loop_var_exited(var_name)
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
            context_label = br.label or "if"
            result, candidate_binding = self._eval_condition_with_binding(
                br.condition, state, runtime_ctx, context_label=context_label
            )
            label = br.label or f"branch-{idx}"
            if br.label == "unless":
                result = not result
            if br.label == "guard":
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

    async def _execute_ir_match(self, stmt: IRMatch, state: FlowState, runtime_ctx: FlowRuntimeContext, prefix: str) -> None:
        evaluator = self._build_evaluator(state, runtime_ctx)
        try:
            target_val = evaluator.evaluate(stmt.target) if stmt.target is not None else None
        except EvaluationError as exc:
            message = "I couldn't evaluate the value used in this match. Check the expression before match."
            detail = str(exc).strip()
            if detail:
                message = f"{message} {detail}"
            raise Namel3ssError(message) from exc
        matched = False
        for idx, br in enumerate(stmt.branches):
            if matched:
                break
            if self._match_branch(br, target_val, evaluator, state):
                matched = True
                for action_idx, action in enumerate(br.actions):
                    label = br.label or f"branch-{idx}"
                    await self._execute_statement(action, state, runtime_ctx, f"{prefix}.{label}.{action_idx}")
        return state.get("last_output")

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
            if stmt.pattern:
                self._apply_destructuring(stmt.pattern, value, env, state, is_constant=stmt.is_constant)
                state.set("last_output", value)
                return value
            env.declare(stmt.name, value, is_constant=stmt.is_constant)
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
            items = self._require_list_iterable(
                iterable_val,
                context="repeat for each",
                detail="Make sure the expression after in evaluates to a list of items.",
            )
            if stmt.pattern:
                pattern = stmt.pattern
                target_names = (
                    [f.alias or f.name for f in pattern.fields] if pattern.kind == "record" else list(pattern.fields)
                )
                prev_values = {name: env.resolve(name) for name in target_names if env.has(name)}
                declared: set[str] = set()
                for idx, item in enumerate(items):
                    if pattern.kind == "record":
                        if not isinstance(item, dict):
                            raise Namel3ssError("N3-3300: repeat for each requires a list of records for this pattern.")
                        for field in pattern.fields:
                            target_name = field.alias or field.name
                            if field.name not in item:
                                raise Namel3ssError(
                                    build_missing_field_error(
                                        field.name,
                                        item,
                                        context=f"I can't destructure field {field.name} from this record.",
                                    )
                                )
                            if env.has(target_name):
                                env.assign(target_name, item.get(field.name))
                            else:
                                env.declare(target_name, item.get(field.name))
                                declared.add(target_name)
                            state.set(target_name, item.get(field.name))
                    elif pattern.kind == "list":
                        if not isinstance(item, (list, tuple)):
                            raise Namel3ssError("Cannot destructure list; expected a list/sequence.")
                        fields = pattern.fields
                        if len(item) < len(fields):
                            raise Namel3ssError(
                                f"Cannot destructure list into [{', '.join(fields)}]; it has only {len(item)} elements."
                            )
                        for idx_name, name in enumerate(fields):
                            if env.has(name):
                                env.assign(name, item[idx_name] if idx_name < len(item) else None)
                            else:
                                env.declare(name, item[idx_name] if idx_name < len(item) else None)
                                declared.add(name)
                            state.set(name, item[idx_name] if idx_name < len(item) else None)
                    for body_stmt in stmt.body:
                        await self._execute_statement(body_stmt, state, runtime_ctx, f"{prefix}.foreach{idx}", allow_return=allow_return)
                        if state.context.get("__awaiting_input__"):
                            break
                    if state.context.get("__awaiting_input__"):
                        break
                for name in target_names:
                    if name in prev_values:
                        env.assign(name, prev_values[name])
                        state.set(name, prev_values[name])
                    else:
                        env.remove(name)
                        if hasattr(env, "mark_loop_var_exited"):
                            env.mark_loop_var_exited(name)
                        state.data.pop(name, None)
                return state.get("last_output")
            else:
                had_prev = env.has(stmt.var_name)
                prev_val = env.resolve(stmt.var_name) if had_prev else None
                declared_new = False
                for idx, item in enumerate(items):
                    if had_prev or declared_new:
                        env.assign(stmt.var_name, item)
                    else:
                        env.declare(stmt.var_name, item)
                        declared_new = True
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
                    if hasattr(env, "mark_loop_var_exited"):
                        env.mark_loop_var_exited(stmt.var_name)
                    state.data.pop(stmt.var_name, None)
                return state.get("last_output")
        if isinstance(stmt, IRRepeatUpTo):
            count_val = evaluator.evaluate(stmt.count) if stmt.count is not None else 0
            count_num = self._coerce_non_negative_int(count_val, context="repeat up to", unit="times")
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
            attempts = self._coerce_non_negative_int(count_val, context="retry up to", unit="attempts")
            if attempts == 0:
                return state.get("last_output")
            last_output = state.get("last_output")
            for attempt in range(attempts):
                try:
                    for body_stmt in stmt.body:
                        last_output = await self._execute_statement(body_stmt, state, runtime_ctx, f"{prefix}.retry{attempt}", allow_return=allow_return)
                        if state.context.get("__awaiting_input__"):
                            break
                    if state.context.get("__awaiting_input__"):
                        break
                    if self._is_error_result(last_output):
                        if attempt + 1 == attempts:
                            raise Namel3ssError(
                                f"This retry block failed after {attempts} attempts.\nThe last result looked like an error: {self._format_condition_value(last_output)}."
                            )
                        if stmt.with_backoff:
                            await self._sleep_backoff(attempt)
                        continue
                    break
                except Exception as exc:
                    if attempt + 1 == attempts:
                        raise
                    if stmt.with_backoff:
                        await self._sleep_backoff(attempt)
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

        resolved_kind = self._resolve_step_kind(node)
        step_name = node.config.get("step_name", node.id)
        timeout = node.config.get("timeout_seconds")
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

    async def _run_ai_stage(
        self,
        ai_name: str,
        payload: dict[str, Any],
        runtime_ctx: FlowRuntimeContext,
        step_name: str,
        flow_name: str,
        base_context: ExecutionContext,
    ) -> Any:
        ai_call = getattr(runtime_ctx.program, "ai_calls", {}).get(ai_name) if runtime_ctx else None
        if not ai_call:
            raise Namel3ssError(f"Stage '{step_name}' refers to AI '{ai_name}', but that AI is not declared.")
        try:
            return await self._call_ai_step(
                ai_call=ai_call,
                base_context=base_context,
                runtime_ctx=runtime_ctx,
                step_name=step_name,
                flow_name=flow_name,
                tools_mode=None,
            )
        except Exception:
            text_val = payload.get("question") or payload.get("context") if isinstance(payload, dict) else ""
            return text_val or f"{ai_name} output"

    def _evaluate_stage_number(self, expr: Any, evaluator: ExpressionEvaluator, default: int | None = None) -> int:
        if expr is None:
            return int(default or 0)
        if isinstance(expr, int):
            return expr
        if isinstance(expr, ast_nodes.Literal):
            try:
                return int(expr.value)
            except Exception:
                return int(default or 0)
        try:
            val = evaluator.evaluate(expr) if isinstance(expr, ast_nodes.Expr) else expr
            return int(val)
        except Exception:
            return int(default or 0)

    async def _run_rag_pipeline(
        self,
        pipeline_name: str,
        question: str,
        state: FlowState,
        runtime_ctx: FlowRuntimeContext,
        base_context: ExecutionContext,
        flow_name: str,
        step_name: str,
    ) -> dict[str, Any]:
        pipeline = getattr(runtime_ctx, "rag_pipelines", {}).get(pipeline_name) or getattr(self.program, "rag_pipelines", {}).get(pipeline_name)
        if not pipeline:
            raise Namel3ssError(
                f"Step '{step_name}' refers to RAG pipeline '{pipeline_name}', but no such pipeline is declared."
            )
        ctx = {
            "original_question": question,
            "current_query": question,
            "queries": [],
            "subquestions": [],
            "chosen_vector_stores": [],
            "matches": [],
            "matches_per_stage": {},
            "context": "",
            "answer": None,
        }
        evaluator = self._build_evaluator(state, runtime_ctx)
        for stage in pipeline.stages:
            st_type = (stage.type or "").lower()
            if st_type == "ai_rewrite":
                result = await self._run_ai_stage(
                    ai_name=stage.ai or "",
                    payload={"question": question, "context": ctx.get("context")},
                    runtime_ctx=runtime_ctx,
                    step_name=stage.name,
                    flow_name=flow_name,
                    base_context=base_context,
                )
                ctx["current_query"] = str(result)
            elif st_type == "query_route":
                result = await self._run_ai_stage(
                    ai_name=stage.ai or "",
                    payload={"question": question, "context": ctx.get("context")},
                    runtime_ctx=runtime_ctx,
                    step_name=stage.name,
                    flow_name=flow_name,
                    base_context=base_context,
                )
                choices = stage.choices or []
                selected: list[str] = []
                if isinstance(result, list):
                    selected = [str(x) for x in result if str(x)]
                elif isinstance(result, dict):
                    selected = [str(v) for v in result.values() if v]
                elif result is not None:
                    selected = [str(result)]
                selected_filtered = [s for s in selected if not choices or s in choices]
                if not selected_filtered and pipeline.default_vector_store:
                    selected_filtered = [pipeline.default_vector_store]
                if not selected_filtered:
                    raise Namel3ssError(
                        f"Stage '{stage.name}' in pipeline '{pipeline.name}' could not choose a vector_store. Ensure the router AI returns one of: {', '.join(choices)}."
                    )
                ctx["chosen_vector_stores"] = selected_filtered
            elif st_type == "vector_retrieve":
                targets: list[str] = []
                if stage.vector_store:
                    targets = [stage.vector_store]
                elif ctx.get("chosen_vector_stores"):
                    targets = list(ctx.get("chosen_vector_stores") or [])
                elif pipeline.default_vector_store:
                    targets = [pipeline.default_vector_store]
                if not targets:
                    raise Namel3ssError(
                        f"Stage '{stage.name}' in pipeline '{pipeline.name}' must specify a 'vector_store' or set a default with 'use vector_store \"...\"'."
                    )
                top_k_val = self._evaluate_stage_number(stage.top_k, evaluator, default=5)
                if top_k_val < 1:
                    top_k_val = 5
                queries_to_run = ctx.get("queries") or ctx.get("subquestions") or []
                if not queries_to_run:
                    queries_to_run = [ctx.get("current_query") or question]
                aggregated_matches: list[dict[str, Any]] = []
                where_expr = stage.where
                for target_vs in targets:
                    for query_text in queries_to_run:
                        matches = runtime_ctx.vectorstores.query(target_vs, query_text, top_k=top_k_val, frames=runtime_ctx.frames)
                        filtered_matches = []
                        if where_expr is None:
                            filtered_matches = matches
                        else:
                            for m in matches:
                                env = VariableEnvironment({"metadata": m.get("metadata") or {}, "match": m})
                                match_eval = ExpressionEvaluator(
                                    env,
                                    resolver=lambda name, meta=m: (
                                        True,
                                        meta.get("metadata", {}).get(name) if isinstance(meta, dict) and isinstance(meta.get("metadata"), dict) and name in meta.get("metadata", {}) else meta.get(name),
                                    ),
                                )
                                try:
                                    keep_val = match_eval.evaluate(where_expr)
                                except EvaluationError as exc:
                                    raise Namel3ssError(str(exc)) from exc
                                if not isinstance(keep_val, bool):
                                    raise Namel3ssError(
                                        f"The 'where' clause on stage '{stage.name}' in pipeline '{pipeline.name}' must be a boolean expression."
                                    )
                                if keep_val:
                                    filtered_matches.append(m)
                        for m in filtered_matches:
                            m = dict(m)
                            m.setdefault("vector_store", target_vs)
                            m.setdefault("query", query_text)
                            aggregated_matches.append(m)
                ctx["matches"] = aggregated_matches
                ctx_matches_per_stage = ctx.get("matches_per_stage") or {}
                ctx_matches_per_stage[stage.name] = aggregated_matches
                ctx["matches_per_stage"] = ctx_matches_per_stage
                texts: list[str] = []
                for m in aggregated_matches:
                    text_val = m.get("text") if isinstance(m, dict) else None
                    if text_val is None and isinstance(m, dict):
                        meta = m.get("metadata") or {}
                        if isinstance(meta, dict):
                            text_val = meta.get("text")
                    if text_val:
                        texts.append(str(text_val))
                ctx["context"] = "\n\n".join(texts).strip()
            elif st_type == "ai_rerank":
                matches = ctx.get("matches") or []
                top_k_val = self._evaluate_stage_number(stage.top_k, evaluator, default=len(matches) or 0)
                try:
                    await self._run_ai_stage(
                        ai_name=stage.ai or "",
                        payload={"question": question, "matches": matches},
                        runtime_ctx=runtime_ctx,
                        step_name=stage.name,
                        flow_name=flow_name,
                        base_context=base_context,
                    )
                except Exception:
                    pass
                matches_sorted = sorted(matches, key=lambda m: m.get("score", 0), reverse=True)
                if top_k_val > 0:
                    matches_sorted = matches_sorted[:top_k_val]
                ctx["matches"] = matches_sorted
                ctx_matches_per_stage = ctx.get("matches_per_stage") or {}
                ctx_matches_per_stage[stage.name] = matches_sorted
                ctx["matches_per_stage"] = ctx_matches_per_stage
                ctx["context"] = "\n\n".join([str(m.get("text", "")) for m in matches_sorted if m.get("text")]).strip()
            elif st_type == "context_compress":
                max_tokens_val = self._evaluate_stage_number(stage.max_tokens, evaluator, default=None)
                context_text = ctx.get("context") or ""
                if max_tokens_val and max_tokens_val > 0 and len(context_text) > max_tokens_val:
                    ctx["context"] = context_text[:max_tokens_val]
            elif st_type == "multi_query":
                result = await self._run_ai_stage(
                    ai_name=stage.ai or "",
                    payload={"question": question, "context": ctx.get("context"), "current_query": ctx.get("current_query")},
                    runtime_ctx=runtime_ctx,
                    step_name=stage.name,
                    flow_name=flow_name,
                    base_context=base_context,
                )
                queries: list[str] = []
                if isinstance(result, list):
                    queries = [str(q) for q in result if str(q)]
                elif isinstance(result, str):
                    queries = [s for s in [r.strip() for r in result.split("\n") if r.strip()] if s]
                elif result is not None:
                    queries = [str(result)]
                max_queries_val = self._evaluate_stage_number(stage.max_queries, evaluator, default=4)
                if max_queries_val > 0:
                    queries = queries[:max_queries_val]
                ctx["queries"] = queries
            elif st_type == "query_decompose":
                result = await self._run_ai_stage(
                    ai_name=stage.ai or "",
                    payload={"question": question, "context": ctx.get("context")},
                    runtime_ctx=runtime_ctx,
                    step_name=stage.name,
                    flow_name=flow_name,
                    base_context=base_context,
                )
                subs: list[str] = []
                if isinstance(result, list):
                    subs = [str(s) for s in result if str(s)]
                elif isinstance(result, str):
                    subs = [s for s in [r.strip() for r in result.split("\n") if r.strip()] if s]
                elif result is not None:
                    subs = [str(result)]
                max_sub_val = self._evaluate_stage_number(stage.max_subquestions, evaluator, default=3)
                if max_sub_val > 0:
                    subs = subs[:max_sub_val]
                ctx["subquestions"] = subs
            elif st_type == "fusion":
                source_matches: list[dict[str, Any]] = []
                missing_sources: list[str] = []
                for ref in stage.from_stages or []:
                    ref_matches = (ctx.get("matches_per_stage") or {}).get(ref)
                    if ref_matches is None:
                        missing_sources.append(ref)
                        continue
                    source_matches.append({"name": ref, "matches": ref_matches})
                if missing_sources:
                    raise Namel3ssError(
                        f"Stage '{stage.name}' in pipeline '{pipeline.name}' cannot fuse missing stages: {', '.join(missing_sources)}."
                    )
                fused_scores: dict[tuple[Any, Any], dict[str, Any]] = {}
                method = (stage.method or "rrf").lower()
                for entry in source_matches:
                    matches_list = entry["matches"]
                    for rank, m in enumerate(matches_list):
                        key = (m.get("id"), m.get("vector_store"))
                        base = fused_scores.setdefault(key, {"score": 0.0, "match": dict(m)})
                        if method == "rrf":
                            base["score"] += 1.0 / float(rank + 1)
                        else:
                            base["score"] += 1.0 / float(rank + 1)
                fused_list = []
                for val in fused_scores.values():
                    match = val["match"]
                    match["score"] = val.get("score", match.get("score", 0))
                    fused_list.append(match)
                fused_list.sort(key=lambda m: m.get("score", 0), reverse=True)
                top_k_val = self._evaluate_stage_number(stage.top_k, evaluator, default=5)
                if top_k_val > 0:
                    fused_list = fused_list[:top_k_val]
                ctx["matches"] = fused_list
                ctx_matches_per_stage = ctx.get("matches_per_stage") or {}
                ctx_matches_per_stage[stage.name] = fused_list
                ctx["matches_per_stage"] = ctx_matches_per_stage
                ctx["context"] = "\n\n".join([str(m.get("text", "")) for m in fused_list if m.get("text")]).strip()
            elif st_type == "ai_answer":
                answer_val = await self._run_ai_stage(
                    ai_name=stage.ai or "",
                    payload={"question": question, "context": ctx.get("context"), "matches": ctx.get("matches")},
                    runtime_ctx=runtime_ctx,
                    step_name=stage.name,
                    flow_name=flow_name,
                    base_context=base_context,
                )
                ctx["answer"] = answer_val if not isinstance(answer_val, dict) else answer_val.get("text") or answer_val
            else:
                raise Namel3ssError(f"Stage type '{stage.type}' is not supported in RAG pipelines.")
        return {
            "answer": ctx.get("answer"),
            "matches": ctx.get("matches"),
            "context": ctx.get("context"),
            "query": ctx.get("current_query"),
        }

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
        alias_map = getattr(runtime_ctx, "step_aliases", {}) if runtime_ctx else {}
        if "." in name:
            parts = name.split(".")
            base = parts[0]
            if alias_map and base in alias_map:
                step_name = alias_map[base]
                output_key = f"step.{step_name}.output"
                if output_key not in state.data:
                    raise EvaluationError(
                        f"The step alias {base} refers to {step_name}, which hasn't run yet in this flow. Move the code that reads {base}.output after the {step_name} step."
                    )
                value: Any = state.get(output_key)
                remainder = parts[1:]
                if remainder and remainder[0] == "output":
                    remainder = remainder[1:]
                for part in remainder:
                    if isinstance(value, dict) and part in value:
                        value = value.get(part)
                    elif hasattr(value, part):
                        value = getattr(value, part, None)
                    else:
                        raise EvaluationError(
                            build_missing_field_error(
                                part,
                                value,
                                context=f"I don't know field {part} on this record.",
                            )
                        )
                return True, value
            if runtime_ctx and runtime_ctx.frames and base in getattr(runtime_ctx.frames, "frames", {}):
                current: Any = runtime_ctx.frames.query(base)
                for part in parts[1:]:
                    if isinstance(current, dict) and part in current:
                        current = current.get(part)
                    elif hasattr(current, part):
                        current = getattr(current, part, None)
                    else:
                        return False, None
                return True, current
            allowed_roots = {"state", "user", "secret", "input", "env", "step"}
            if base not in allowed_roots:
                raise EvaluationError(
                    f"There is no step alias called {base} in this flow. Add 'step is \"{base}\" as {base}:' or use step.{base}.output instead."
                )
            if base == "user":
                user_ctx = (runtime_ctx.user_context if runtime_ctx else None) or state.context.get("user") or {}
                value: Any = user_ctx
                for part in parts[1:]:
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        value = getattr(value, part, None)
                return True, value
            if base == "secret":
                secrets_mgr = (runtime_ctx.secrets if runtime_ctx else None) or self.secrets
                if len(parts) == 1:
                    return True, secrets_mgr
                key = ".".join(parts[1:])
                if secrets_mgr:
                    return True, secrets_mgr.get(key)
                return True, None
            if base == "state":
                if len(parts) == 1:
                    return True, state.data
                field = parts[1]
                if field in state.data:
                    value: Any = state.get(field)
                    for part in parts[2:]:
                        if isinstance(value, dict) and part in value:
                            value = value.get(part)
                        elif hasattr(value, part):
                            value = getattr(value, part, None)
                        else:
                            raise EvaluationError(f"state.{field} is not defined")
                    return True, value
                raise EvaluationError(f"state.{field} is not defined")
            if base == "input":
                value = state.context.get("input") if state.context else None
                if runtime_ctx and getattr(runtime_ctx, "execution_context", None):
                    value = value or getattr(runtime_ctx.execution_context, "user_input", None)
                for part in parts[1:]:
                    if isinstance(value, dict) and part in value:
                        value = value.get(part)
                    elif hasattr(value, part):
                        value = getattr(value, part, None)
                    else:
                        return False, None
                return True, value
            if base == "env":
                env_obj = state.context.get("env") if state.context else None
                try:
                    import os  # locally scoped to avoid global dependency
                except Exception:  # pragma: no cover
                    os = None
                if env_obj is None and os is not None:
                    env_obj = os.environ
                value: Any = env_obj
                for part in parts[1:]:
                    if isinstance(value, dict) and part in value:
                        value = value.get(part)
                    elif hasattr(value, part):
                        value = getattr(value, part, None)
                    else:
                        return False, None
                return True, value
            if base == "step":
                if len(parts) < 2:
                    return False, None
                step_name = parts[1]
                output_key = f"step.{step_name}.output"
                if output_key not in state.data:
                    raise EvaluationError(f"The step {step_name} has not produced output yet.")
                value: Any = state.get(output_key)
                remainder = parts[2:]
                if remainder and remainder[0] == "output":
                    remainder = remainder[1:]
                for part in remainder:
                    if isinstance(value, dict) and part in value:
                        value = value.get(part)
                    elif hasattr(value, part):
                        value = getattr(value, part, None)
                    else:
                        raise EvaluationError(
                            build_missing_field_error(
                                part,
                                value,
                                context=f"I don't know field {part} on this record.",
                            )
                        )
                return True, value
            return False, None
        if alias_map and name in alias_map:
            step_name = alias_map[name]
            output_key = f"step.{step_name}.output"
            if output_key not in state.data:
                raise EvaluationError(
                    f"The step alias {name} refers to {step_name}, which hasn't run yet in this flow. Move the code that reads {name}.output after the {step_name} step."
                )
            return True, state.get(output_key)
        if runtime_ctx and runtime_ctx.frames and name in getattr(runtime_ctx.frames, "frames", {}):
            return True, runtime_ctx.frames.query(name)
        return False, None

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
            return isinstance(target_val, bool) and target_val is pat_val
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

    def _collect_step_aliases(self, items: list[IRFlowStep | IRFlowLoop | IRTransactionBlock]) -> dict[str, str]:
        aliases: dict[str, str] = {}

        def walk(steps: list[IRFlowStep | IRFlowLoop | IRTransactionBlock]) -> None:
            for step in steps:
                if isinstance(step, IRFlowLoop):
                    walk(step.body)
                    continue
                if isinstance(step, IRTransactionBlock):
                    walk(step.body)
                    continue
                if step.alias:
                    if step.alias in aliases:
                        raise Namel3ssError(f"Step alias '{step.alias}' is already used for step '{aliases[step.alias]}'. Aliases must be unique within a flow.")
                    aliases[step.alias] = step.name

        walk(items)
        return aliases

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

    async def _execute_tool_call(self, node, state: FlowState, runtime_ctx: FlowRuntimeContext, tool_override=None):
        target = node.config.get("target") if isinstance(node.config, dict) else None
        tool_cfg = tool_override or runtime_ctx.tool_registry.get(target)
        if not tool_cfg:
            raise Namel3ssError(f'I couldn\'t find a tool named "{target}". Check your configuration or plugin setup.')

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
        if not arg_values:
            default_message = state.get("last_output")
            if default_message is None:
                default_message = state.get("slug")
            arg_values = {"message": default_message}

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

        if getattr(tool_cfg, "url_expr", None) is None and getattr(tool_cfg, "url_template", None) is None:
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

    def _evaluate_bulk_source(
        self,
        source_expr: ast_nodes.Expr,
        evaluator: ExpressionEvaluator,
        step_name: str,
        label: str,
    ) -> list[Any]:
        try:
            value = evaluator.evaluate(source_expr)
        except Exception as exc:
            raise Namel3ssError(
                f"I couldn’t evaluate {label} in step '{step_name}': {exc}"
            ) from exc
        if value is None:
            return []
        if not isinstance(value, list):
            raise Namel3ssError(
                f"I expected {label} to be a list, but got {type(value).__name__} instead."
            )
        return value

    def _evaluate_where_conditions(
        self,
        conditions: object,
        evaluator: ExpressionEvaluator,
        step_name: str,
        record: Any | None,
    ) -> dict | None:
        """Evaluate WHERE conditions into a normalized boolean tree."""
        if not conditions:
            return None
        allowed_ops = {"eq", "neq", "gt", "lt", "ge", "le", "in", "is_null", "is_not_null"}

        def _eval_leaf(cond_obj: object) -> dict:
            if isinstance(cond_obj, (IRConditionLeaf, ast_nodes.ConditionLeaf, ast_nodes.RecordWhereCondition)):
                field_name = cond_obj.field_name
                op = cond_obj.op
                value_expr = getattr(cond_obj, "value", None) or getattr(cond_obj, "value_expr", None)
                cond_span = getattr(cond_obj, "span", None)
            elif isinstance(cond_obj, dict) and {"field", "op"} <= set(cond_obj.keys()):
                field_name = cond_obj.get("field")
                op = cond_obj.get("op")
                value_expr = cond_obj.get("value")
                cond_span = cond_obj.get("span")
            else:
                raise Namel3ssError(
                    "I don't understand this condition in a WHERE block. Use is, is not, is greater than, is at least, or is one of []."
                )
            if op not in allowed_ops:
                raise Namel3ssError(
                    "I don't understand this condition in a WHERE block. Use is, is not, is greater than, is at least, is at most, is one of, or null checks."
                )
            if record:
                field = record.fields.get(field_name)
                if not field:
                    raise Namel3ssError(
                        f"Record '{record.name}' has no field named '{field_name}' (step '{step_name}')."
                    )
            else:
                field = None
            if op in {"is_null", "is_not_null"}:
                return {"type": "leaf", "field": field_name, "op": op, "value": None, "span": cond_span}
            try:
                raw_value = evaluator.evaluate(value_expr) if isinstance(value_expr, ast_nodes.Expr) else value_expr
            except Exception as exc:
                raise Namel3ssError(
                    f"Failed to evaluate a WHERE condition for field '{field_name}' in step '{step_name}': {exc}"
                ) from exc
            if op == "in":
                if not isinstance(raw_value, (list, tuple, set)):
                    raise Namel3ssError(
                        "I don't understand this condition in the WHERE block. 'is one of' needs a list of values."
                    )
                if field:
                    value = [
                        self._coerce_record_value(record.name, field, item, step_name) for item in list(raw_value)
                    ]
                else:
                    value = list(raw_value)
            else:
                value = (
                    self._coerce_record_value(record.name, field, raw_value, step_name)
                    if field
                    else raw_value
                )
            return {"type": "leaf", "field": field_name, "op": op, "value": value, "span": cond_span}

        def _combine_list(children: list[dict | None]) -> dict | None:
            valid = [c for c in children if c is not None]
            if not valid:
                return None
            current = valid[0]
            for child in valid[1:]:
                current = {"type": "and", "left": current, "right": child}
            return current

        def _transform(cond_obj: object | None) -> dict | None:
            if cond_obj is None:
                return None
            if isinstance(cond_obj, dict) and cond_obj.get("type") in {"leaf", "and", "or", "all", "any"}:
                return cond_obj
            if isinstance(cond_obj, (IRConditionLeaf, ast_nodes.ConditionLeaf, ast_nodes.RecordWhereCondition)):
                return _eval_leaf(cond_obj)
            if isinstance(cond_obj, IRConditionAnd) or isinstance(cond_obj, ast_nodes.ConditionAnd):
                left = _transform(cond_obj.left)
                right = _transform(cond_obj.right)
                return {"type": "and", "left": left, "right": right, "span": getattr(cond_obj, "span", None)}
            if isinstance(cond_obj, IRConditionOr) or isinstance(cond_obj, ast_nodes.ConditionOr):
                left = _transform(cond_obj.left)
                right = _transform(cond_obj.right)
                return {"type": "or", "left": left, "right": right, "span": getattr(cond_obj, "span", None)}
            if isinstance(cond_obj, IRConditionAllGroup) or isinstance(cond_obj, ast_nodes.ConditionAllGroup):
                children = [_transform(c) for c in getattr(cond_obj, "children", [])]
                children = [c for c in children if c is not None]
                return {"type": "all", "children": children, "span": getattr(cond_obj, "span", None)}
            if isinstance(cond_obj, IRConditionAnyGroup) or isinstance(cond_obj, ast_nodes.ConditionAnyGroup):
                children = [_transform(c) for c in getattr(cond_obj, "children", [])]
                children = [c for c in children if c is not None]
                return {"type": "any", "children": children, "span": getattr(cond_obj, "span", None)}
            if isinstance(cond_obj, list):
                return _combine_list([_transform(c) for c in cond_obj])
            if isinstance(cond_obj, dict):
                # Treat dict with field/op/value as a single leaf.
                return _eval_leaf(cond_obj)
            raise Namel3ssError(
                "I don't understand this condition in a WHERE block. Use is, is not, is greater than, is at least, is one of, or null checks."
            )

        return _transform(conditions)

    def _condition_tree_matches(self, condition: dict | None, row: dict, alias: str) -> bool:
        if condition is None:
            return True

        def _ensure_bool(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            raise Namel3ssError(
                f"I expected this condition in find {alias} where: to be true or false, but it evaluated to {value!r} instead."
            )

        def _eval(node: dict | None) -> bool:
            if node is None:
                return True
            ntype = node.get("type")
            if ntype is None and "field" in node:
                ntype = "leaf"
            if ntype == "leaf":
                field = node.get("field")
                op = node.get("op")
                value = node.get("value")
                row_val = row.get(field)
                try:
                    if op == "eq":
                        return _ensure_bool(row_val == value)
                    if op == "neq":
                        return _ensure_bool(row_val != value)
                    if op == "gt":
                        return _ensure_bool(row_val > value)
                    if op == "lt":
                        return _ensure_bool(row_val < value)
                    if op == "ge":
                        return _ensure_bool(row_val >= value)
                    if op == "le":
                        return _ensure_bool(row_val <= value)
                    if op == "in":
                        if not isinstance(value, (list, tuple, set)):
                            raise Namel3ssError(
                                f"I expected this condition in find {alias} where: to compare against a list."
                            )
                        return _ensure_bool(row_val in value)
                    if op == "is_null":
                        return _ensure_bool(row_val is None)
                    if op == "is_not_null":
                        return _ensure_bool(row_val is not None)
                except Namel3ssError:
                    raise
                except Exception as exc:
                    raise Namel3ssError(
                        f"I couldn't evaluate this condition in find {alias} where: {exc}"
                    ) from exc
                raise Namel3ssError(
                    "I don't understand this condition in a WHERE block. Use is, is not, is greater than, is at least, is one of, or null checks."
                )
            if ntype == "and":
                left = node.get("left")
                right = node.get("right")
                return _eval(left) and _eval(right)
            if ntype == "or":
                left = node.get("left")
                right = node.get("right")
                return _eval(left) or _eval(right)
            if ntype == "all":
                for child in node.get("children") or []:
                    if not _eval(child):
                        return False
                return True
            if ntype == "any":
                for child in node.get("children") or []:
                    if _eval(child):
                        return True
                return False
            raise Namel3ssError(
                "I don't understand this condition in a WHERE block. Use is, is not, is greater than, is at least, is one of, or null checks."
            )

        return bool(_eval(condition))

    def _sort_rows(self, rows: list[dict], order_by: list[Any], alias: str) -> list[dict]:
        def get_value(row: dict, field: str):
            if not isinstance(row, dict) or field not in row:
                raise Namel3ssError(
                    f"I can't sort {alias} by {field} because some rows don't have that field."
                )
            return row.get(field)

        sorted_rows = list(rows)
        for item in reversed(order_by):
            field = getattr(item, "field_name", None) or (item.get("field_name") if isinstance(item, dict) else None)
            direction = getattr(item, "direction", None) or (item.get("direction") if isinstance(item, dict) else None) or "asc"
            reverse = str(direction).lower() == "desc"
            try:
                sorted_rows = sorted(sorted_rows, key=lambda r, f=field: get_value(r, f), reverse=reverse)
            except Namel3ssError:
                raise
            except Exception as exc:
                raise Namel3ssError(
                    f"I couldn't sort {alias} because the sort keys are not comparable: {exc}"
                ) from exc
        return sorted_rows

    def _resolve_record_default_value(self, record_name: str, field, step_name: str) -> Any:
        default_value = getattr(field, "default", None)
        if default_value is None:
            return None
        if default_value == "now":
            if getattr(field, "type", None) != "datetime":
                raise Namel3ssError(
                    f"I can't use this default for field {field.name} on record {record_name} because it doesn't match the field type."
                )
            raw_value = datetime.utcnow()
        else:
            raw_value = default_value
        try:
            return self._coerce_record_value(record_name, field, raw_value, step_name)
        except Namel3ssError:
            raise Namel3ssError(
                f"I can't use this default for field {field.name} on record {record_name} because it doesn't match the field type."
            )

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
                    return value
                if isinstance(value, str):
                    return datetime.fromisoformat(value)
                raise ValueError("expected datetime or ISO-8601 string")
            if ftype == "decimal":
                if isinstance(value, Decimal):
                    return value
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return Decimal(str(value))
                if isinstance(value, str):
                    return Decimal(value)
                raise ValueError("expected decimal-compatible value")
            if ftype == "array":
                if isinstance(value, list):
                    return value
                if isinstance(value, tuple):
                    return list(value)
                if isinstance(value, str):
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return parsed
                    raise ValueError("expected JSON array string")
                raise ValueError("expected list or array-like value")
            if ftype == "json":
                if isinstance(value, (dict, list)):
                    return value
                if isinstance(value, str):
                    parsed = json.loads(value)
                    if isinstance(parsed, (dict, list)):
                        return parsed
                    raise ValueError("expected JSON object or array string")
                raise ValueError("expected JSON object or array value")
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
                raise Namel3ssError(f"N3L-1502: I can't create a {record.name} record because required field {key} is missing.")
            normalized[key] = coerced
        if include_defaults:
            for key, field in record.fields.items():
                if key in normalized:
                    continue
                if field.default is not None:
                    normalized[key] = self._resolve_record_default_value(record.name, field, step_name)
                elif enforce_required and field.required:
                    raise Namel3ssError(f"N3L-1502: I can't create a {record.name} record because required field {key} is missing.")
        if enforce_required:
            for key, field in record.fields.items():
                if (field.required or field.primary_key) and normalized.get(key) is None:
                    raise Namel3ssError(f"N3L-1502: I can't create a {record.name} record because required field {key} is missing.")
        return normalized

    def _format_unique_violation_error(
        self,
        record_name: str,
        field_name: str,
        value: Any,
        scope_label: str | None,
    ) -> str:
        value_display = f"\"{value}\"" if isinstance(value, str) else str(value)
        record_lower = record_name.lower()
        if scope_label:
            return (
                f'I can’t save this {record_name} because {field_name} {value_display} is already used inside this {scope_label}.\n'
                f"Each {record_lower} must have a unique {field_name} within {scope_label.lower()}."
            )
        return (
            f'I can’t save this {record_name} because {field_name} {value_display} is already used.\n'
            f"Each {record_lower} must have a unique {field_name}."
        )

    def _format_missing_scope_value_error(
        self,
        record_name: str,
        field_name: str,
        scope_label: str,
        scope_field: str,
    ) -> str:
        return (
            f'I can’t enforce must be unique within "{scope_label}" on {record_name}.{field_name} because I can’t find a value for {scope_field} on this record.\n'
            f"Provide {scope_field} before saving or remove that uniqueness rule."
        )

    def _format_foreign_key_violation_error(
        self,
        record_name: str,
        field_name: str,
        value: Any,
        target_record: str,
    ) -> str:
        value_display = f"\"{value}\"" if isinstance(value, str) else str(value)
        return (
            f'I can’t save this {record_name} because {field_name} {value_display} does not point to an existing {target_record}.\n'
            f"Make sure you use a valid {target_record} id here."
        )

    def _enforce_record_uniqueness(
        self,
        record,
        candidate_row: dict[str, Any],
        existing_row: dict[str, Any] | None,
        frames,
        frame_name: str,
        operation: str,
    ) -> None:
        pk_name = getattr(record, "primary_key", None)
        pk_value = None
        if pk_name:
            if operation == "update" and existing_row is not None:
                pk_value = existing_row.get(pk_name)
            else:
                pk_value = candidate_row.get(pk_name)
        for field in record.fields.values():
            if not getattr(field, "is_unique", False):
                continue
            new_value = candidate_row.get(field.name)
            if new_value is None:
                continue
            scope_label = getattr(field, "unique_scope", None)
            scope_field = getattr(field, "unique_scope_field", None)
            scope_value = None
            if scope_label:
                if not scope_field:
                    raise Namel3ssError(
                        f'I can’t enforce must be unique within "{scope_label}" on {record.name}.{field.name} because I can’t resolve the scope field.'
                    )
                scope_value = candidate_row.get(scope_field)
                if scope_value is None:
                    raise Namel3ssError(
                        self._format_missing_scope_value_error(record.name, field.name, scope_label, scope_field)
                    )
            if existing_row is not None:
                previous_value = existing_row.get(field.name)
                scope_changed = False
                if scope_field:
                    previous_scope = existing_row.get(scope_field)
                    scope_changed = previous_scope != scope_value
                if previous_value == new_value and not scope_changed:
                    continue
            filters = [{"field": field.name, "op": "eq", "value": new_value}]
            if scope_field:
                filters.append({"field": scope_field, "op": "eq", "value": scope_value})
            matches = frames.query(frame_name, filters)
            for row in matches:
                if operation == "update" and pk_name and row.get(pk_name) == pk_value:
                    continue
                raise Namel3ssError(
                    self._format_unique_violation_error(record.name, field.name, new_value, scope_label)
                )

    def _enforce_record_foreign_keys(
        self,
        record,
        candidate_row: dict[str, Any],
        existing_row: dict[str, Any] | None,
        frames,
        runtime_records: dict[str, Any] | None,
        operation: str,
    ) -> None:
        if not runtime_records:
            runtime_records = {}
        for field in record.fields.values():
            target_record_name = getattr(field, "references_record", None)
            target_field_name = getattr(field, "reference_target_field", None)
            if not target_record_name or not target_field_name:
                continue
            new_value = candidate_row.get(field.name)
            if new_value is None:
                continue
            if existing_row is not None:
                previous_value = existing_row.get(field.name)
                if previous_value == new_value:
                    continue
            target_record = runtime_records.get(target_record_name)
            if not target_record:
                raise Namel3ssError(
                    f'I can’t enforce references "{target_record_name}" on {record.name}.{field.name} because record "{target_record_name}" is not available at runtime.'
                )
            target_frame = getattr(target_record, "frame", None)
            if not target_frame:
                raise Namel3ssError(
                    f'I can’t enforce references "{target_record_name}" on {record.name}.{field.name} because the referenced record has no frame.'
                )
            filters = [
                {
                    "field": target_field_name,
                    "op": "eq",
                    "value": new_value,
                }
            ]
            matches = frames.query(target_frame, filters)
            if not matches:
                raise Namel3ssError(
                    self._format_foreign_key_violation_error(record.name, field.name, new_value, target_record_name)
                )

    def _validate_record_field_values(
        self,
        record,
        candidate_row: dict[str, Any],
    ) -> None:
        for field in record.fields.values():
            value = candidate_row.get(field.name)
            self._validate_single_field_value(record, field, value)

    def _validate_single_field_value(self, record, field, value: Any) -> None:
        if value is None:
            return
        enum_values = getattr(field, "enum_values", None)
        if enum_values:
            if value not in enum_values:
                allowed_label = "[" + ", ".join(self._format_validation_value(val) for val in enum_values) + "]"
                raise Namel3ssError(
                    self._format_validation_error(
                        record.name,
                        f"{field.name} must be one of {allowed_label} but got {self._format_validation_value(value)}.",
                    )
                )
        numeric_min = getattr(field, "numeric_min", None)
        if numeric_min is not None and value < numeric_min:
            raise Namel3ssError(
                self._format_validation_error(
                    record.name,
                    f"{field.name} must be at least {self._format_validation_value(numeric_min)} but got {self._format_validation_value(value)}.",
                )
            )
        numeric_max = getattr(field, "numeric_max", None)
        if numeric_max is not None and value > numeric_max:
            raise Namel3ssError(
                self._format_validation_error(
                    record.name,
                    f"{field.name} must be at most {self._format_validation_value(numeric_max)} but got {self._format_validation_value(value)}.",
                )
            )
        length_min = getattr(field, "length_min", None)
        length_max = getattr(field, "length_max", None)
        if length_min is not None or length_max is not None:
            unit = "items"
            if isinstance(value, str):
                current_length = len(value)
                unit = "characters"
            elif isinstance(value, (list, tuple)):
                current_length = len(value)
            else:
                current_length = None
            if current_length is not None:
                if length_min is not None and current_length < length_min:
                    raise Namel3ssError(
                        self._format_validation_error(
                            record.name,
                            f"{field.name} must have length at least {length_min} {unit} but got {current_length}.",
                        )
                    )
                if length_max is not None and current_length > length_max:
                    raise Namel3ssError(
                        self._format_validation_error(
                            record.name,
                            f"{field.name} must have length at most {length_max} {unit} but got {current_length}.",
                        )
                    )
        pattern = getattr(field, "pattern", None)
        if pattern:
            if not isinstance(value, str):
                raise Namel3ssError(
                    self._format_validation_error(
                        record.name,
                        f"{field.name} must match pattern \"{pattern}\" but got {self._format_validation_value(value)}.",
                    )
                )
            if not re.fullmatch(pattern, value):
                raise Namel3ssError(
                    self._format_validation_error(
                        record.name,
                        f"{field.name} must match pattern \"{pattern}\" but got {self._format_validation_value(value)}.",
                    )
                )

    def _format_validation_error(self, record_name: str, message: str) -> str:
        return f"I can't save this {record_name} because {message}"

    def _format_validation_value(self, value: Any) -> str:
        if isinstance(value, str):
            return f'"{value}"'
        return str(value)

    def _track_pending_uniques(
        self,
        record,
        candidate_row: dict[str, Any],
        tracker: dict[tuple[str, Any | None], set[Any]],
    ) -> None:
        for field in record.fields.values():
            if not getattr(field, "is_unique", False):
                continue
            value = candidate_row.get(field.name)
            if value is None:
                continue
            scope_field = getattr(field, "unique_scope_field", None)
            scope_label = getattr(field, "unique_scope", None)
            scope_value = candidate_row.get(scope_field) if scope_field else None
            if scope_field and scope_value is None:
                continue
            key = (field.name, scope_value if scope_field else None)
            seen = tracker.setdefault(key, set())
            if value in seen:
                raise Namel3ssError(
                    self._format_unique_violation_error(record.name, field.name, value, scope_label)
                )
            seen.add(value)

    def _apply_relationship_joins(
        self,
        record,
        rows: list[dict[str, Any]],
        relationships: list,
        runtime_ctx: FlowRuntimeContext,
    ) -> list[dict[str, Any]]:
        if not rows or not relationships:
            return rows
        frames = runtime_ctx.frames
        if frames is None:
            raise Namel3ssError("Frame registry unavailable for relationship queries.")
        runtime_records = getattr(runtime_ctx, "records", {}) or {}
        for join in relationships:
            target_record_name = getattr(join, "target_record", None)
            target_field = getattr(join, "target_field", None)
            attachment_field = getattr(join, "attachment_field", None) or join.related_alias
            via_field = join.via_field
            if not target_record_name or not target_field:
                raise Namel3ssError(
                    f"I can’t load related records for '{attachment_field}' because the relationship metadata is incomplete."
                )
            target_record = runtime_records.get(target_record_name)
            if not target_record:
                raise Namel3ssError(
                    f'I can’t load related {target_record_name} records because "{target_record_name}" is not registered at runtime.'
                )
            target_frame = getattr(target_record, "frame", None)
            if not target_frame:
                raise Namel3ssError(
                    f'I can’t load related {target_record_name} records because "{target_record_name}" is missing a frame binding.'
                )
            fk_values = {row.get(via_field) for row in rows if row.get(via_field) is not None}
            related_map: dict[Any, dict[str, Any]] = {}
            if fk_values:
                filters = [{"field": target_field, "op": "in", "value": list(fk_values)}]
                related_rows = frames.query(target_frame, filters)
                for rel_row in related_rows:
                    rel_dict = dict(rel_row)
                    key = rel_dict.get(target_field)
                    if key is not None:
                        related_map[key] = rel_dict
            for row in rows:
                fk_value = row.get(via_field)
                if fk_value is None:
                    row[attachment_field] = None
                else:
                    row[attachment_field] = related_map.get(fk_value)
        return rows

    def _evaluate_pagination_expr(
        self,
        expr: ast_nodes.Expr | None,
        evaluator: ExpressionEvaluator,
        step_name: str,
        label: str,
        default: int | None = None,
    ) -> int | None:
        if expr is None:
            return default
        try:
            value = evaluator.evaluate(expr) if isinstance(expr, ast_nodes.Expr) else expr
        except Exception as exc:
            raise Namel3ssError(f"I expected a non-negative number for {label}, but couldn't evaluate it: {exc}") from exc
        if value is None:
            return default
        if not isinstance(value, (int, float)):
            raise Namel3ssError(
                f"I expected a non-negative number for {label}, but got {value} instead."
            )
        number = int(value)
        if number < 0:
            raise Namel3ssError(f"I expected a non-negative number for {label}, but got {value} instead.")
        return number

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
            self._validate_record_field_values(record, normalized)
            candidate_row = dict(normalized)
            self._enforce_record_uniqueness(
                record,
                candidate_row,
                None,
                frames,
                frame_name,
                operation="create",
            )
            self._enforce_record_foreign_keys(
                record,
                candidate_row,
                None,
                frames,
                getattr(runtime_ctx, "records", None),
                operation="create",
            )
            frames.insert(frame_name, normalized)
            return dict(normalized)
        if kind == "db_bulk_create":
            bulk_spec = params.get("bulk_create")
            if not isinstance(bulk_spec, IRBulkCreateSpec):
                raise Namel3ssError("I need create many ... details to run this bulk create step.")
            expr_label = self._expr_to_str(bulk_spec.source_expr)
            source_label = f"create many {record.name} from {expr_label or 'that expression'}"
            source_value = self._evaluate_bulk_source(bulk_spec.source_expr, evaluator, step_name, source_label)
            if not source_value:
                return []
            local_uniques: dict[tuple[str, Any | None], set[Any]] = {}
            runtime_records = getattr(runtime_ctx, "records", None)
            prepared_rows: list[dict[str, Any]] = []
            for idx, item in enumerate(source_value, start=1):
                if not isinstance(item, dict):
                    raise Namel3ssError(
                        f"Item {idx} inside create many {record.name} must be a record of field values, but I received {type(item).__name__}."
                    )
                normalized = self._prepare_record_values(
                    record,
                    item,
                    step_name,
                    include_defaults=True,
                    enforce_required=True,
                )
                self._validate_record_field_values(record, normalized)
                candidate_row = dict(normalized)
                self._enforce_record_uniqueness(
                    record,
                    candidate_row,
                    None,
                    frames,
                    frame_name,
                    operation="create",
                )
                self._enforce_record_foreign_keys(
                    record,
                    candidate_row,
                    None,
                    frames,
                    runtime_records,
                    operation="create",
                )
                self._track_pending_uniques(record, candidate_row, local_uniques)
                prepared_rows.append(normalized)
            inserted_rows: list[dict[str, Any]] = []
            for row in prepared_rows:
                frames.insert(frame_name, row)
                inserted_rows.append(dict(row))
            return inserted_rows
        if kind in {"find", "db_get"}:
            query_obj = params.get("query")
            alias = record.name.lower()
            where_values = None
            order_values = None
            limit_expr = None
            offset_expr = None
            filters_tree = None
            if isinstance(query_obj, IRRecordQuery):
                alias = query_obj.alias or alias
                where_values = query_obj.where_condition
                order_values = query_obj.order_by
                limit_expr = query_obj.limit_expr
                offset_expr = query_obj.offset_expr
            else:
                where_values = params.get("where")
                order_values = params.get("order_by")
                limit_expr = params.get("limit")
                offset_expr = params.get("offset")
            by_id_values = self._evaluate_expr_dict(params.get("by_id"), evaluator, step_name, "by id")
            filters: list[dict[str, Any]] = []
            used_primary = False
            if record.primary_key and record.primary_key in by_id_values:
                pk_field = record.fields.get(record.primary_key)
                if pk_field:
                    filters.append(
                        {
                            "field": record.primary_key,
                            "op": "eq",
                            "value": self._coerce_record_value(
                                record.name,
                                pk_field,
                                by_id_values[record.primary_key],
                                step_name,
                            ),
                        }
                    )
                    used_primary = True
            elif where_values:
                filters_tree = self._evaluate_where_conditions(where_values, evaluator, step_name, record)
            if used_primary:
                rows = list(frames.query(frame_name, filters))
            else:
                rows = list(frames.query(frame_name, None))
                if filters_tree:
                    rows = [row for row in rows if self._condition_tree_matches(filters_tree, row, alias or record.name)]
            if order_values:
                rows = self._sort_rows(rows, order_values, alias or record.name)
            offset_value = self._evaluate_pagination_expr(offset_expr, evaluator, step_name, f"offset {alias} by", default=0)
            if offset_value:
                rows = rows[offset_value:]
            limit_value = self._evaluate_pagination_expr(limit_expr, evaluator, step_name, f"limit {alias} to")
            if limit_value is not None:
                rows = rows[:limit_value]
            rows = [dict(row) for row in rows]
            if isinstance(query_obj, IRRecordQuery) and getattr(query_obj, "relationships", None):
                rows = self._apply_relationship_joins(
                    record,
                    rows,
                    query_obj.relationships,
                    runtime_ctx,
                )
            if used_primary:
                return rows[0] if rows else None
            return rows
        if kind == "db_update":
            by_id_values = self._evaluate_expr_dict(params.get("by_id"), evaluator, step_name, "by id")
            if not record.primary_key or record.primary_key not in by_id_values:
                raise Namel3ssError(
                    f"Step '{step_name}' must include primary key '{record.primary_key}' inside 'by id'."
                )
            pk_field = record.fields.get(record.primary_key)
            filters = [
                {
                    "field": record.primary_key,
                    "op": "eq",
                    "value": self._coerce_record_value(
                        record.name,
                        pk_field,
                        by_id_values[record.primary_key],
                        step_name,
                    ),
                }
            ]
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
            existing_row = dict(rows[0])
            candidate_row = dict(existing_row)
            candidate_row.update(updates)
            self._validate_record_field_values(record, candidate_row)
            self._enforce_record_uniqueness(
                record,
                candidate_row,
                existing_row,
                frames,
                frame_name,
                operation="update",
            )
            self._enforce_record_foreign_keys(
                record,
                candidate_row,
                existing_row,
                frames,
                getattr(runtime_ctx, "records", None),
                operation="update",
            )
            for row in rows:
                row.update(updates)
            return dict(rows[0])
        if kind == "db_bulk_update":
            bulk_spec = params.get("bulk_update")
            if not isinstance(bulk_spec, IRBulkUpdateSpec):
                raise Namel3ssError("I need update many ... where: details to run this bulk update step.")
            set_entries = params.get("set")
            if not isinstance(set_entries, dict) or not set_entries:
                raise Namel3ssError(f"I need a 'set:' block inside update many {record.name.lower()}s to know which fields to change.")
            evaluated_updates = self._evaluate_expr_dict(set_entries, evaluator, step_name, "set")
            normalized_updates = self._prepare_record_values(
                record,
                evaluated_updates,
                step_name,
                include_defaults=False,
                enforce_required=False,
            )
            filters_tree = self._evaluate_where_conditions(bulk_spec.where_condition, evaluator, step_name, record)
            rows = list(frames.query(frame_name, None))
            if filters_tree:
                alias_label = bulk_spec.alias or record.name
                rows = [row for row in rows if self._condition_tree_matches(filters_tree, row, alias_label)]
            if not rows:
                return []
            runtime_records = getattr(runtime_ctx, "records", None)
            local_uniques: dict[tuple[str, Any | None], set[Any]] = {}
            staged_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for row in rows:
                existing_row = dict(row)
                candidate_row = dict(existing_row)
                candidate_row.update(normalized_updates)
                self._validate_record_field_values(record, candidate_row)
                self._enforce_record_uniqueness(
                    record,
                    candidate_row,
                    existing_row,
                    frames,
                    frame_name,
                    operation="update",
                )
                self._enforce_record_foreign_keys(
                    record,
                    candidate_row,
                    existing_row,
                    frames,
                    runtime_records,
                    operation="update",
                )
                self._track_pending_uniques(record, candidate_row, local_uniques)
                staged_rows.append((row, candidate_row))
            for row, _candidate in staged_rows:
                row.update(normalized_updates)
            return [dict(row) for row in rows]
        if kind == "db_delete":
            by_id_values = self._evaluate_expr_dict(params.get("by_id"), evaluator, step_name, "by id")
            if not record.primary_key or record.primary_key not in by_id_values:
                raise Namel3ssError(
                    f"Step '{step_name}' must include primary key '{record.primary_key}' inside 'by id'."
                )
            pk_field = record.fields.get(record.primary_key)
            filters = [
                {
                    "field": record.primary_key,
                    "op": "eq",
                    "value": self._coerce_record_value(
                        record.name,
                        pk_field,
                        by_id_values[record.primary_key],
                        step_name,
                    ),
                }
            ]
            deleted = frames.delete(frame_name, filters)
            return {"ok": deleted > 0, "deleted": deleted}
        if kind == "db_bulk_delete":
            bulk_spec = params.get("bulk_delete")
            if not isinstance(bulk_spec, IRBulkDeleteSpec):
                raise Namel3ssError("I need delete many ... where: details to run this bulk delete step.")
            filters_tree = self._evaluate_where_conditions(bulk_spec.where_condition, evaluator, step_name, record)
            if not filters_tree:
                raise Namel3ssError("delete many ... must include a 'where:' block to limit which records are removed.")
            deleted = frames.delete(frame_name, filters_tree)
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

    def _require_list_iterable(self, value: Any, *, context: str, detail: str | None = None) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        message = f"{context} expects a list, but I got {self._format_condition_value(value)} instead."
        if detail:
            message = f"{message}\n{detail}"
        raise Namel3ssError(message)

    def _coerce_non_negative_int(self, value: Any, *, context: str, unit: str) -> int:
        message = f"{context} expects a non-negative number of {unit}, but I got {self._format_condition_value(value)} instead."
        if isinstance(value, bool) or not isinstance(value, numbers.Real):
            raise Namel3ssError(message)
        if value < 0:
            raise Namel3ssError(message)
        if isinstance(value, float) and not value.is_integer():
            raise Namel3ssError(message)
        return int(value)

    async def _sleep_backoff(self, attempt: int) -> None:
        base = getattr(self, "retry_config", None).backoff_base if getattr(self, "retry_config", None) else 0
        delay = base * (2**attempt)
        if delay > 0:
            await asyncio.sleep(delay)

    def _format_condition_value(self, value: Any) -> str:
        try:
            rendered = repr(value)
        except Exception:
            rendered = f"<{value.__class__.__name__}>"
        if len(rendered) > 120:
            rendered = f"{rendered[:117]}..."
        return rendered

    def _condition_descriptor(self, context_label: str | None) -> str:
        if not context_label or context_label == "condition":
            return "condition"
        if context_label.endswith("condition"):
            return context_label
        return f"{context_label} condition"

    def _eval_condition_with_binding(
        self,
        expr: ast_nodes.Expr | None,
        state: FlowState,
        runtime_ctx: FlowRuntimeContext,
        *,
        context_label: str = "condition",
    ) -> tuple[bool, Any]:
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
            descriptor = self._condition_descriptor(context_label)
            raise Namel3ssError(
                "This "
                + descriptor
                + " did not evaluate to a boolean value.\n"
                + f"I got {self._format_condition_value(value)} instead. Make sure the condition returns true or false."
            )
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
