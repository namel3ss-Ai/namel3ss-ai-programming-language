from __future__ import annotations

import numbers
from typing import Any

from ... import ast_nodes
from ...errors import Namel3ssError
from ...runtime.expressions import EvaluationError, ExpressionEvaluator
from ..errors import ReturnSignal
from ..graph import FlowRuntimeContext, FlowState
from ...ir import (
    IRConditionAllGroup,
    IRConditionAnd,
    IRConditionAnyGroup,
    IRConditionLeaf,
    IRConditionOr,
    IRMatchBranch,
)

__all__ = ["FlowEngineConditionMixin"]


class FlowEngineConditionMixin:
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
        if isinstance(conditions, dict) and conditions and not (
            {"field", "op"} <= set(conditions.keys()) or conditions.get("type") in {"leaf", "and", "or", "all", "any"}
        ):
            conditions = [{"field": key, "op": "eq", "value": value} for key, value in conditions.items()]
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
