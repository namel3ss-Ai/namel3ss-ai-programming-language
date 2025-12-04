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

from ..agent.engine import AgentRunner
from ..ai.registry import ModelRegistry
from ..ai.router import ModelRouter
from ..errors import Namel3ssError
from ..ir import IRFlow, IRProgram
from ..metrics.tracker import MetricsTracker
from ..runtime.context import ExecutionContext, execute_ai_call_with_registry
from ..secrets.manager import SecretsManager
from ..tools.registry import ToolRegistry
from .graph import FlowError, FlowGraph, FlowNode, FlowRuntimeContext, FlowState, flow_ir_to_graph
from .models import FlowRunResult, FlowStepMetrics, FlowStepResult
from ..observability.tracing import default_tracer
from ..observability.metrics import default_metrics


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
        )

    def run_flow(
        self, flow: IRFlow, context: ExecutionContext, initial_state: Optional[dict[str, Any]] = None
    ) -> FlowRunResult:
        return asyncio.run(self.run_flow_async(flow, context, initial_state=initial_state))

    async def run_flow_async(
        self, flow: IRFlow, context: ExecutionContext, initial_state: Optional[dict[str, Any]] = None
    ) -> FlowRunResult:
        graph = flow_ir_to_graph(flow)
        if context.tracer:
            context.tracer.start_flow(flow.name)
            context.tracer.record_flow_graph_build(flow.name, graph)

        runtime_ctx = self._build_runtime_context(context)
        state = FlowState(
            data=initial_state or {},
            context={
                "flow_name": flow.name,
                "request_id": context.request_id,
                "app": context.app_name,
            },
        )

        result = await self.a_run_flow(graph, state, runtime_ctx, flow_name=flow.name)
        if context.tracer:
            context.tracer.end_flow()
        return result

    async def a_run_flow(
        self, graph: FlowGraph, state: FlowState, runtime_ctx: FlowRuntimeContext, flow_name: str | None = None
    ) -> FlowRunResult:
        step_results: list[FlowStepResult] = []
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
        return FlowRunResult(
            flow_name=flow_name or graph.entry_id,
            steps=step_results,
            state=final_state,
            errors=final_state.errors,
            step_metrics=step_metrics,
            total_cost=total_cost,
            total_duration_seconds=total_duration,
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
        return state

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
                return float(getattr(output, "cost"))
            except Exception:
                return 0.0
        return 0.0


class TimedStepError(Exception):
    def __init__(self, original: Exception, duration: float) -> None:
        message = str(original) or "timeout"
        super().__init__(message)
        self.original = original
        self.duration = duration
