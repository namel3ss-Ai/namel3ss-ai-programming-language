from __future__ import annotations

from typing import Any

from ... import ast_nodes
from ...errors import Namel3ssError
from ...runtime.expressions import EvaluationError, VariableEnvironment
from ...ir import IRAction
from ..graph import FlowNode, FlowRuntimeContext, FlowState

__all__ = ["_run_condition_node", "_eval_rulegroup", "_eval_expr", "_match_pattern"]

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
