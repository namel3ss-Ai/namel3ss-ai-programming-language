from __future__ import annotations

import asyncio
from typing import Any, Callable, Optional

from ...errors import Namel3ssError
from ...runtime.expressions import VariableEnvironment
from ..graph import FlowNode, FlowRuntimeContext, FlowState

__all__ = ["FlowEngineInlineMixin"]


class FlowEngineInlineMixin:
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
