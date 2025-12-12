from __future__ import annotations

import inspect
from typing import Any

from ... import ast_nodes
from ...errors import Namel3ssError
from ...runtime.expressions import EvaluationError, VariableEnvironment
from ..errors import ReturnSignal
from ..graph import FlowRuntimeContext, FlowState
from ..models import StreamEvent
from ...ir import (
    IRAction,
    IRAskUser,
    IRCheckpoint,
    IRFlowLoop,
    IRFlowStep,
    IRForm,
    IRIf,
    IRLet,
    IRLog,
    IRMatch,
    IRNote,
    IRReturn,
    IRRetry,
    IRSet,
    IRStatement,
    IRTryCatch,
    IRForEach,
    IRRepeatUpTo,
)

__all__ = ["FlowEngineScriptMixin"]


class FlowEngineScriptMixin:
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
        has_result_pattern = any(isinstance(br.pattern, (ast_nodes.SuccessPattern, ast_nodes.ErrorPattern)) for br in stmt.branches)
        has_otherwise = any(br.pattern is None for br in stmt.branches)
        normalized_result = self._normalize_result(target_val) if has_result_pattern else None
        if has_result_pattern and normalized_result is None and not has_otherwise:
            flow_label = state.context.get("flow_name") or "flow"
            value_snippet = self._format_condition_value(target_val)
            raise Namel3ssError(
                f"match with 'when success' or 'when error' expects a result-like value (e.g. a tool or agent result) in {flow_label} at {prefix}. I got {value_snippet}. Add an 'otherwise' branch or provide a result."
            )
        matched = False
        for idx, br in enumerate(stmt.branches):
            if matched:
                break
            if self._match_branch(br, target_val, evaluator, state, normalized_result=normalized_result):
                matched = True
                for action_idx, action in enumerate(br.actions):
                    label = br.label or f"branch-{idx}"
                    await self._execute_statement(action, state, runtime_ctx, f"{prefix}.{label}.{action_idx}")
        if has_result_pattern and not matched and not has_otherwise:
            flow_label = state.context.get("flow_name") or "flow"
            value_snippet = self._format_condition_value(target_val)
            raise Namel3ssError(
                f"No matching success/error branch in match at {flow_label}:{prefix} for value {value_snippet}. Add an 'otherwise' branch or ensure the result sets ok/ error fields."
            )
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

    async def _execute_statement(self, stmt: IRStatement, state: FlowState, runtime_ctx: FlowRuntimeContext, prefix: str, allow_return: bool = True) -> Any:
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
            return await self._execute_ir_match(stmt, state, runtime_ctx, prefix)
        if isinstance(stmt, IRReturn):
            if not allow_return:
                raise Namel3ssError("N3-6002: return used outside helper")
            value = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
            value = self._coerce_return_value(value)
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

    async def _execute_script(self, statements: list[IRStatement] | None, state: FlowState, runtime_ctx: FlowRuntimeContext, step_id: str, allow_return: bool = True) -> Any:
        last_val: Any = None
        for idx, stmt in enumerate(statements or []):
            last_val = await self._execute_statement(stmt, state, runtime_ctx, f"{step_id}.stmt{idx}", allow_return=allow_return)
            if state.context.get("__awaiting_input__"):
                break
        return last_val
