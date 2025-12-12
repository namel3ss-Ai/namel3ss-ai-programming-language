from __future__ import annotations

from typing import Any

from ... import ast_nodes
from ...errors import Namel3ssError
from ...runtime.expressions import EvaluationError, ExpressionEvaluator, VariableEnvironment, build_missing_field_error
from ..graph import FlowRuntimeContext, FlowState
from ...ir import IRFlowLoop, IRFlowStep, IRTransactionBlock, IRLet, IRSet, IRReturn

__all__ = ["FlowEngineExpressionMixin"]


class FlowEngineExpressionMixin:
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
