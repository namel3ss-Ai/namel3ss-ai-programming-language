"""
Flow execution engine V3: graph-based runtime with branching, parallelism, and
error boundaries.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from typing import Any, Callable, Optional
from uuid import uuid4

from .. import ast_nodes
from ..agent.engine import AgentRunner
from ..ai.registry import ModelRegistry
from ..ai.router import ModelRouter
from ..errors import Namel3ssError
from ..ir import IRAction, IRFlow, IRIf, IRLet, IRProgram, IRSet, IRStatement
from ..metrics.tracker import MetricsTracker
from ..observability.metrics import default_metrics
from ..observability.tracing import default_tracer
from ..runtime.context import ExecutionContext, execute_ai_call_with_registry
from ..runtime.expressions import EvaluationError, ExpressionEvaluator, VariableEnvironment
from ..secrets.manager import SecretsManager
from ..tools.registry import ToolRegistry
from .graph import (
    FlowError,
    FlowGraph,
    FlowNode,
    FlowRuntimeContext,
    FlowState,
    flow_ir_to_graph,
)
from .models import FlowRunResult, FlowStepMetrics, FlowStepResult


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
    ) -> None:
        self.program = program
        self.model_registry = model_registry
        self.tool_registry = tool_registry
        self.agent_runner = agent_runner
        self.router = router
        self.metrics = metrics
        self.secrets = secrets
        self.max_parallel_tasks = max_parallel_tasks

    def _build_runtime_context(self, context: ExecutionContext) -> FlowRuntimeContext:
        return FlowRuntimeContext(
            program=self.program,
            model_registry=self.model_registry,
            tool_registry=self.tool_registry,
            agent_runner=self.agent_runner,
            router=self.router,
            tracer=context.tracer,
            metrics=context.metrics or self.metrics,
            secrets=context.secrets or self.secrets,
            memory_engine=context.memory_engine,
            rag_engine=context.rag_engine,
            execution_context=context,
            max_parallel_tasks=self.max_parallel_tasks,
            parallel_semaphore=asyncio.Semaphore(self.max_parallel_tasks),
            variables=None,
        )

    def run_flow(
        self, flow: IRFlow, context: ExecutionContext, initial_state: Optional[dict[str, Any]] = None
    ) -> FlowRunResult:
        return asyncio.run(self.run_flow_async(flow, context, initial_state=initial_state))

    async def run_flow_async(
        self, flow: IRFlow, context: ExecutionContext, initial_state: Optional[dict[str, Any]] = None
    ) -> FlowRunResult:
        runtime_ctx = self._build_runtime_context(context)
        env = VariableEnvironment(context.variables)
        runtime_ctx.variables = env
        state = FlowState(
            data=initial_state or {},
            context={
                "flow_name": flow.name,
                "request_id": context.request_id,
                "app": context.app_name,
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
                failure = FlowStepResult(
                    step_name=node.config.get("step_name", node.id),
                    kind=node.kind,
                    target=node.config.get("target", node.id),
                    success=False,
                    error_message=str(exc),
                    handled=handled,
                    node_id=node.id,
                    duration_seconds=duration,
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
                    return await run_node(boundary_for_children, current_state, None, stop_at)
                raise

            # Stop execution if a redirect has been requested.
            if current_state.context.get("__redirect_flow__"):
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
        return FlowRunResult(
            flow_name=flow_name or graph.entry_id,
            steps=step_results,
            state=final_state,
            errors=final_state.errors,
            step_metrics=step_metrics,
            total_cost=total_cost,
            total_duration_seconds=total_duration,
            redirect_to=redirect_to,
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
                rag_engine=runtime_ctx.rag_engine,
                tracer=runtime_ctx.tracer,
                tool_registry=runtime_ctx.tool_registry,
                metrics=runtime_ctx.metrics,
                secrets=runtime_ctx.secrets,
            )

        with default_tracer.span(
            f"flow.step.{node.kind}", attributes={"step": step_name, "flow_target": target, "kind": node.kind}
        ):
            if node.kind == "noop":
                output = node.config.get("output")
            elif node.kind == "ai":
                if target not in runtime_ctx.program.ai_calls:
                    raise Namel3ssError(f"Flow AI target '{target}' not found")
                ai_call = runtime_ctx.program.ai_calls[target]
                output = execute_ai_call_with_registry(
                    ai_call, runtime_ctx.model_registry, runtime_ctx.router, base_context
                )
            elif node.kind == "agent":
                output = asdict(runtime_ctx.agent_runner.run(target, base_context))
            elif node.kind == "tool":
                tool = runtime_ctx.tool_registry.get(target)
                if not tool:
                    raise Namel3ssError(f"Flow tool target '{target}' not found")
                tool_kwargs = node.config.get("params") or {}
                tool_kwargs.setdefault("message", state.get("last_output", ""))
                output = tool.run(**tool_kwargs)
                if runtime_ctx.metrics:
                    runtime_ctx.metrics.record_tool_call(provider=target, cost=0.0005)
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
        items = node.config.get("items") or []
        items_path = node.config.get("items_path")
        if items_path:
            items = state.get(items_path, []) or items
        body = node.config.get("body") or []
        max_concurrency = node.config.get("max_concurrency")
        sem = asyncio.Semaphore(max_concurrency) if max_concurrency else None
        results_states: list[FlowState] = []

        async def run_body(item, index: int):
            if sem:
                async with sem:
                    return await self._run_inline_sequence(f"{node.id}.{index}", body, state.copy(), runtime_ctx, loop_item=item)
            return await self._run_inline_sequence(f"{node.id}.{index}", body, state.copy(), runtime_ctx, loop_item=item)

        tasks = [asyncio.create_task(run_body(item, idx)) for idx, item in enumerate(items)]
        for task in tasks:
            results_states.append(await task)
        # Collect outputs
        collected = [st.diff() for st in results_states]
        state.set(f"step.{node.id}.items", collected)
        self._merge_branch_states(state, [f"{node.id}.{i}" for i in range(len(results_states))], results_states)
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

    async def _execute_statement(self, stmt: IRStatement, state: FlowState, runtime_ctx: FlowRuntimeContext, prefix: str) -> Any:
        env = state.variables or runtime_ctx.variables or VariableEnvironment()
        evaluator = self._build_evaluator(state, runtime_ctx)
        if isinstance(stmt, IRLet):
            value = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
            env.declare(stmt.name, value)
            state.set(stmt.name, value)
            state.set("last_output", value)
            return value
        if isinstance(stmt, IRSet):
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
        return last_val

    async def _execute_with_timing(
        self, node: FlowNode, state: FlowState, runtime_ctx: FlowRuntimeContext
    ) -> Optional[FlowStepResult]:
        timeout = node.config.get("timeout_seconds")
        start = time.monotonic()
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
            raise TimedStepError(exc, duration) from exc
        duration = time.monotonic() - start
        if result:
            result.duration_seconds = duration if duration > 0 else 1e-6
            result.cost = self._extract_cost(result.output)
            default_metrics.record_step(result.node_id or result.step_name, result.duration_seconds, result.cost)
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

    def _resolve_identifier(self, name: str, state: FlowState) -> tuple[bool, Any]:
        env = getattr(state, "variables", None)
        if env and env.has(name):
            return True, env.resolve(name)
        parts = name.split(".")
        value: Any = None
        found = False
        if parts[0] in state.data:
            value = state.get(parts[0])
            found = True
        elif parts[0] in state.context:
            value = state.context.get(parts[0])
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

    def _build_evaluator(self, state: FlowState, runtime_ctx: FlowRuntimeContext | None) -> ExpressionEvaluator:
        env = getattr(state, "variables", None) or getattr(runtime_ctx, "variables", None) or VariableEnvironment()
        return ExpressionEvaluator(
            env,
            resolver=lambda name: self._resolve_identifier(name, state),
            rulegroup_resolver=lambda expr: self._eval_rulegroup(expr, state, runtime_ctx) if runtime_ctx else (False, None),
        )

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
        found, subject = self._resolve_identifier(pattern.subject.name, state)
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

        inline_steps = []
        for action in selected.actions:
            if isinstance(action, IRAction):
                cfg = {
                    "kind": action.kind,
                    "target": action.target,
                    "step_name": f"{node.id}.{action.target}",
                    "reason": "conditional",
                }
                if action.message:
                    cfg["params"] = {"message": action.message}
                inline_steps.append(cfg)
            else:
                await self._execute_statement(action, state, runtime_ctx, node.id)
        if inline_steps:
            await self._run_inline_sequence(node.id, inline_steps, state, runtime_ctx)
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
