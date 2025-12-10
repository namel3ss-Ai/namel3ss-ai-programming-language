from __future__ import annotations

import difflib
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Tuple

from .. import ast_nodes
from ..errors import Namel3ssError
from ..ir import (
    IRCollectionDropRowsStep,
    IRCollectionGroupByStep,
    IRCollectionKeepRowsStep,
    IRCollectionPipeline,
    IRCollectionSkipStep,
    IRCollectionSortStep,
    IRCollectionTakeStep,
    IRLet,
)


class EvaluationError(Namel3ssError):
    """Raised when expression evaluation fails."""


UNDEFINED = object()


def build_missing_field_error(field: str, record: Any, *, context: str, include_get_hint: bool = True, code: str = "N3-3300") -> str:
    available: list[str] = []
    if isinstance(record, dict):
        try:
            available = [str(k) for k in record.keys()]
        except Exception:
            available = []
    suggestion = None
    if available:
        matches = difflib.get_close_matches(field, available, n=1, cutoff=0.6)
        suggestion = matches[0] if matches else None
    parts: list[str] = [f"{code}: {context}"]
    if available:
        parts.append(f"Available fields: {', '.join(available)}.")
    if include_get_hint:
        parts.append(f"If this field is optional, use get <record>.{field} otherwise ... instead.")
    if suggestion and suggestion != field:
        parts.append(f"Did you mean {suggestion}?")
    return " ".join(parts)


class VariableEnvironment:
    """Per-run variable environment."""

    def __init__(self, backing: dict[str, Any] | None = None, *, constants: set[str] | None = None) -> None:
        self.values: dict[str, Any] = backing if backing is not None else {}
        self._declared: set[str] = set(self.values.keys())
        self._constants: set[str] = set(constants or [])
        self._expired_loop_vars: set[str] = set()

    def has(self, name: str) -> bool:
        return name in self._declared

    def declare(self, name: str, value: Any, *, is_constant: bool = False) -> None:
        if name in self._declared:
            if name in self._constants or is_constant:
                raise EvaluationError(
                    f"{name} was declared as a constant and cannot be changed. If you need a mutable variable, remove 'constant' from its declaration."
                )
            raise EvaluationError(f"Variable '{name}' is already defined")
        self._expired_loop_vars.discard(name)
        self._declared.add(name)
        self.values[name] = value
        if is_constant:
            self._constants.add(name)

    def assign(self, name: str, value: Any) -> None:
        if name not in self._declared:
            raise EvaluationError(f"Variable '{name}' is not defined")
        if name in self._constants:
            raise EvaluationError(
                f"{name} was declared as a constant and cannot be changed. If you need a mutable variable, remove 'constant' from its declaration."
            )
        self._expired_loop_vars.discard(name)
        self.values[name] = value

    def remove(self, name: str) -> None:
        self._declared.discard(name)
        self._constants.discard(name)
        self.values.pop(name, None)

    def resolve(self, name: str) -> Any:
        if name in self._declared:
            return self.values[name]
        raise EvaluationError(f"Variable '{name}' is not defined")

    def clone(self) -> "VariableEnvironment":
        clone = VariableEnvironment(dict(self.values), constants=set(self._constants))
        clone._expired_loop_vars = set(self._expired_loop_vars)
        return clone

    def mark_loop_var_exited(self, name: str) -> None:
        self._expired_loop_vars.add(name)

    @property
    def expired_loop_vars(self) -> set[str]:
        return self._expired_loop_vars


class ExpressionEvaluator:
    """Runtime evaluator for Namel3ss expressions."""

    def __init__(
        self,
        env: VariableEnvironment,
        resolver: Callable[[str], Tuple[bool, Any]],
        rulegroup_resolver: Callable[[ast_nodes.RuleGroupRefExpr], Tuple[bool, Any]] | None = None,
        helper_resolver: Callable[[str, list[Any]], Any] | None = None,
    ) -> None:
        self.env = env
        self.resolver = resolver
        self.rulegroup_resolver = rulegroup_resolver
        self.helper_resolver = helper_resolver

    def _unknown_identifier(self, name: str) -> None:
        if name in getattr(self.env, "expired_loop_vars", set()):
            raise EvaluationError(f"{name} exists only inside this loop. If you need it later, store it in state or another local.")
        raise EvaluationError(
            f"I don't know what {name} is here. Declare it with 'let {name} be ...' or use state.{name} / user.{name} / step.<name>.output if you meant those."
        )

    def evaluate(self, expr: ast_nodes.Expr) -> Any:
        if isinstance(expr, ast_nodes.Literal):
            return expr.value
        if isinstance(expr, ast_nodes.VarRef):
            dotted = expr.root if not expr.path else ".".join([expr.root] + expr.path)
            # Allow env values (e.g., loop/local) to be resolved directly
            if self.env.has(dotted):
                return self.env.resolve(dotted)
            # Prefer exact env hit on root if present (locals/loop vars stored bare)
            if self.env.has(expr.root):
                value: Any = self.env.resolve(expr.root)
                if expr.path:
                    value = self._resolve_path_value(value, expr.path)
                return value
            found, value = self.resolver(dotted)
            if found:
                return value
            self._unknown_identifier(expr.root if not expr.path else dotted)
        if isinstance(expr, ast_nodes.Identifier):
            if self.env.has(expr.name):
                return self.env.resolve(expr.name)
            if "." in expr.name:
                parts = expr.name.split(".")
                base = parts[0]
                if self.env.has(base):
                    value: Any = self.env.resolve(base)
                    return self._resolve_path_value(value, parts[1:])
            # Support dotted lookups via resolver
            found, value = self.resolver(expr.name)
            if not found:
                self._unknown_identifier(expr.name if "." not in expr.name else expr.name.split(".")[0])
            return value
        if isinstance(expr, ast_nodes.RecordFieldAccess):
            target = self.evaluate(expr.target) if expr.target else None
            if not isinstance(target, dict):
                raise EvaluationError(
                    f"N3-3300: I can only look up fields on a record, but got {self._render_value(target)} instead."
                )
            if expr.field not in target:
                raise EvaluationError(
                    build_missing_field_error(expr.field, target, context=f"I don't know field {expr.field} on this record.")
                )
            return target.get(expr.field)
        if isinstance(expr, ast_nodes.RuleGroupRefExpr):
            if self.rulegroup_resolver:
                result, value = self.rulegroup_resolver(expr)
                return result if result is not None else value
            return False
        if isinstance(expr, ast_nodes.UnaryOp):
            val = self.evaluate(expr.operand) if expr.operand else None
            if expr.op == "not":
                return not bool(val)
            if expr.op == "+":
                return self._numeric_unary(val, 1)
            if expr.op == "-":
                return self._numeric_unary(val, -1)
            raise EvaluationError(f"Unsupported unary operator '{expr.op}'")
        if isinstance(expr, ast_nodes.BinaryOp):
            left = self.evaluate(expr.left) if expr.left else None
            right = self.evaluate(expr.right) if expr.right else None
            op = expr.op
            if op == "and":
                return bool(left) and bool(right)
            if op == "or":
                return bool(left) or bool(right)
            if op == "+":
                if isinstance(left, list) and isinstance(right, list):
                    return left + right
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
            if op in {"+", "-", "*", "/", "%"}:
                lnum = self._to_number(left)
                rnum = self._to_number(right)
                if op == "+":
                    return lnum + rnum
                if op == "-":
                    return lnum - rnum
                if op == "*":
                    return lnum * rnum
                if op == "/":
                    if rnum == 0:
                        raise EvaluationError("Cannot divide by zero")
                    return lnum / rnum
                if op == "%":
                    if rnum == 0:
                        raise EvaluationError("Cannot divide by zero")
                    return lnum % rnum
            if op in {"==", "=", "is"}:
                return left == right
            if op in {"!=", "is not"}:
                return left != right
            if op in {"<", ">", "<=", ">="}:
                try:
                    if op == "<":
                        return left < right
                    if op == ">":
                        return left > right
                    if op == "<=":
                        return left <= right
                    if op == ">=":
                        return left >= right
                except Exception as exc:  # pragma: no cover - defensive
                    raise EvaluationError(f"Invalid comparison for operator '{op}'") from exc
            raise EvaluationError(f"Unsupported operator '{op}'")
        if isinstance(expr, ast_nodes.ListLiteral):
            return [self.evaluate(item) for item in expr.items]
        if isinstance(expr, ast_nodes.RecordLiteral):
            record: dict[str, Any] = {}
            for field in expr.fields:
                if not field.key:
                    raise EvaluationError("N3-3301: invalid record key")
                record[field.key] = self.evaluate(field.value)
            return record
        if isinstance(expr, ast_nodes.IndexExpr):
            seq = self.evaluate(expr.seq) if expr.seq else None
            idx_val = self.evaluate(expr.index) if expr.index else None
            if not isinstance(seq, list):
                raise EvaluationError("N3-3200: indexing requires a list")
            idx_num = self._to_number(idx_val)
            if isinstance(idx_num, float):
                idx_num = int(idx_num)
            idx_num = int(idx_num)
            if idx_num < 0:
                idx_num = len(seq) + idx_num
            if idx_num < 0 or idx_num >= len(seq):
                raise EvaluationError("N3-3205: index out of bounds")
            return seq[int(idx_num)]
        if isinstance(expr, ast_nodes.SliceExpr):
            seq = self.evaluate(expr.seq) if expr.seq else None
            if not isinstance(seq, list):
                raise EvaluationError("N3-3200: slicing requires a list")
            start_val = self.evaluate(expr.start) if expr.start is not None else None
            end_val = self.evaluate(expr.end) if expr.end is not None else None
            start_idx = None if start_val is None else self._to_int_index(start_val)
            end_idx = None if end_val is None else self._to_int_index(end_val)
            return seq[start_idx:end_idx]
        if isinstance(expr, ast_nodes.BuiltinCall):
            return self._eval_builtin_call(expr)
        if isinstance(expr, ast_nodes.ListBuiltinCall):
            return self._eval_builtin(expr)
        if isinstance(expr, ast_nodes.GetRecordFieldWithDefault):
            record_val = self.evaluate(expr.record) if expr.record is not None else None
            if not isinstance(record_val, dict):
                raise EvaluationError(
                    f"I expected a record for 'get ... otherwise ...', but got {self._render_value(record_val)} instead."
                )
            if expr.field is None:
                raise EvaluationError("get ... otherwise ... requires a field name.")
            if expr.field in record_val:
                return record_val.get(expr.field)
            default_val = self.evaluate(expr.default) if expr.default is not None else None
            return default_val
        if isinstance(expr, ast_nodes.HasKeyOnRecord):
            record_val = self.evaluate(expr.record) if expr.record is not None else None
            if not isinstance(record_val, dict):
                raise EvaluationError(
                    f"I expected a record for 'has key ... on ...', but got {self._render_value(record_val)} instead."
                )
            if expr.key is None:
                raise EvaluationError("has key ... on ... requires a key literal.")
            return expr.key in record_val
        if isinstance(expr, ast_nodes.CollectionPipeline):
            ir_steps = []
            for step in expr.steps:
                if isinstance(step, ast_nodes.CollectionKeepRowsStep):
                    ir_steps.append(IRCollectionKeepRowsStep(condition=step.condition))
                elif isinstance(step, ast_nodes.CollectionDropRowsStep):
                    ir_steps.append(IRCollectionDropRowsStep(condition=step.condition))
                elif isinstance(step, ast_nodes.CollectionGroupByStep):
                    ir_steps.append(IRCollectionGroupByStep(key=step.key, body=getattr(step, "body", []) or []))
                elif isinstance(step, ast_nodes.CollectionSortStep):
                    ir_steps.append(
                        IRCollectionSortStep(
                            kind=getattr(step, "kind", "rows"),
                            key=step.key,
                            direction=getattr(step, "direction", "asc"),
                        )
                    )
                elif isinstance(step, ast_nodes.CollectionTakeStep):
                    ir_steps.append(IRCollectionTakeStep(count=step.count))
                elif isinstance(step, ast_nodes.CollectionSkipStep):
                    ir_steps.append(IRCollectionSkipStep(count=step.count))
            ir_pipeline = IRCollectionPipeline(source=expr.source, steps=ir_steps)
            return self._eval_collection_pipeline(ir_pipeline)
        if isinstance(expr, IRCollectionPipeline):
            return self._eval_collection_pipeline(expr)
        if isinstance(expr, ast_nodes.FilterExpression):
            raise EvaluationError(
                "The legacy 'all ... where ...' filter syntax is no longer supported. Use a collection pipeline with 'keep rows where ...' instead."
            )
        if isinstance(expr, ast_nodes.MapExpression):
            raise EvaluationError(
                "The legacy map(...) syntax is no longer supported. Rewrite this as a collection pipeline or build the list with append/insert helpers."
            )
        if isinstance(expr, ast_nodes.AnyExpression):
            source = self.evaluate(expr.source) if expr.source else None
            if not isinstance(source, list):
                raise EvaluationError("N3-4200: 'any'/'all' requires a list value")
            had_prev = self.env.has(expr.var_name)
            prev_val = self.env.resolve(expr.var_name) if had_prev else None
            result = False
            declared_new = False
            try:
                for item in source:
                    if had_prev:
                        self.env.assign(expr.var_name, item)
                    else:
                        self.env.declare(expr.var_name, item)
                        had_prev = True
                        declared_new = True
                    pred_val = self.evaluate(expr.predicate) if expr.predicate else False
                    if not isinstance(pred_val, bool):
                        raise EvaluationError("N3-4201: predicate must yield boolean")
                    if pred_val:
                        result = True
                        break
            finally:
                if declared_new:
                    self.env.remove(expr.var_name)
                elif had_prev:
                    self.env.assign(expr.var_name, prev_val)
            return result
        if isinstance(expr, ast_nodes.AllExpression):
            source = self.evaluate(expr.source) if expr.source else None
            if not isinstance(source, list):
                raise EvaluationError("N3-4200: 'any'/'all' requires a list value")
            had_prev = self.env.has(expr.var_name)
            prev_val = self.env.resolve(expr.var_name) if had_prev else None
            result = True
            declared_new = False
            try:
                for item in source:
                    if had_prev:
                        self.env.assign(expr.var_name, item)
                    else:
                        self.env.declare(expr.var_name, item)
                        had_prev = True
                        declared_new = True
                    pred_val = self.evaluate(expr.predicate) if expr.predicate else False
                    if not isinstance(pred_val, bool):
                        raise EvaluationError("N3-4201: predicate must yield boolean")
                    if not pred_val:
                        result = False
                        break
            finally:
                if declared_new:
                    self.env.remove(expr.var_name)
                elif had_prev:
                    self.env.assign(expr.var_name, prev_val)
            return result
        if isinstance(expr, ast_nodes.FunctionCall):
            args = [self.evaluate(arg) for arg in expr.args]
            if self.helper_resolver:
                return self.helper_resolver(expr.name, args)
            raise EvaluationError(f"N3-6000: unknown helper '{expr.name}'")
        raise EvaluationError("Unsupported expression")

    def _to_number(self, value: Any) -> float | int:
        if isinstance(value, bool):
            raise EvaluationError("Arithmetic on non-numeric values")
        if isinstance(value, (int, float)):
            return value
        raise EvaluationError("Arithmetic on non-numeric values")

    def _to_int_index(self, value: Any) -> int:
        num = self._to_number(value)
        if isinstance(num, float):
            num = int(num)
        return int(num)

    def _numeric_unary(self, value: Any, sign: int) -> float | int:
        num = self._to_number(value)
        return num if sign > 0 else -num

    def _numeric_value(self, value: Any, code: str = "N3-4102") -> float | int:
        if isinstance(value, bool):
            raise EvaluationError(f"{code}: invalid type for numeric builtin")
        if isinstance(value, (int, float)):
            return value
        raise EvaluationError(f"{code}: invalid type for numeric builtin")

    def _eval_builtin(self, call: ast_nodes.ListBuiltinCall) -> Any:
        name = (call.name or "").lower()
        args = [self.evaluate(call.expr)] if call.expr is not None else []
        return self._dispatch_builtin(name, args)

    def _eval_builtin_call(self, call: ast_nodes.BuiltinCall) -> Any:
        name = (call.name or "").lower()
        args = [self.evaluate(arg) for arg in call.args]
        return self._dispatch_builtin(name, args)

    def _dispatch_builtin(self, name: str, args: list[Any]) -> Any:
        def _ensure_list(arg: Any, context: str) -> list[Any]:
            if not isinstance(arg, list):
                raise EvaluationError(f"I expected a list for {context}, but got {self._render_value(arg)} instead.")
            return arg

        def _ensure_numeric(value: Any, context: str) -> float | int:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise EvaluationError(f"I expected a list of numbers for {context}, but {self._render_value(value)} is not a number.")
            return value

        if name in {"length", "count"}:
            arg = args[0] if args else None
            seq = _ensure_list(arg, f"{name}")
            return len(seq)
        if name in {"first"}:
            arg = args[0] if args else None
            seq = _ensure_list(arg, "first")
            if not seq:
                raise EvaluationError("I can't take the first element of an empty list.")
            return seq[0]
        if name in {"last"}:
            arg = args[0] if args else None
            seq = _ensure_list(arg, "last")
            if not seq:
                raise EvaluationError("I can't take the last element of an empty list.")
            return seq[-1]
        if name in {"reverse"}:
            arg = args[0] if args else None
            seq = _ensure_list(arg, "reverse")
            return list(reversed(seq))
        if name in {"unique"}:
            arg = args[0] if args else None
            seq = _ensure_list(arg, "unique")
            seen = set()
            unique_items = []
            for item in seq:
                try:
                    marker = item
                    is_new = marker not in seen
                except Exception:
                    is_new = item not in unique_items
                if is_new:
                    try:
                        seen.add(item)
                    except Exception:
                        pass
                    unique_items.append(item)
            return unique_items
        if name in {"sorted"}:
            arg = args[0] if args else None
            seq = _ensure_list(arg, "sorted")
            try:
                return sorted(seq)
            except Exception:
                raise EvaluationError("I couldn't sort these values because the sort keys are not comparable.")
        if name in {"sum"}:
            arg = args[0] if args else None
            seq = _ensure_list(arg, "sum")
            total = 0
            for item in seq:
                num = _ensure_numeric(item, "sum")
                total += num
            return total
        if name in {"trim", "lowercase", "uppercase", "slugify"}:
            arg = args[0] if args else None
            if not isinstance(arg, str):
                raise EvaluationError("N3-4000: string builtin is not applicable to the provided type")
            if name == "trim":
                return arg.strip()
            if name == "lowercase":
                return arg.lower()
            if name == "uppercase":
                return arg.upper()
            slug = arg.lower()
            slug = re.sub(r"[\s_]+", "-", slug)
            slug = re.sub(r"[^a-z0-9-]", "", slug)
            slug = re.sub(r"-{2,}", "-", slug).strip("-")
            return slug
        if name == "replace":
            if len(args) != 3:
                raise EvaluationError("N3-4003: replace arguments must be strings")
            base, old, new = args
            if not isinstance(base, str) or not isinstance(old, str) or not isinstance(new, str):
                raise EvaluationError("N3-4003: replace arguments must be strings")
            return base.replace(old, new)
        if name == "split":
            if len(args) != 2:
                raise EvaluationError("N3-4002: 'split' requires a string separator")
            base, sep = args
            if not isinstance(base, str):
                raise EvaluationError("N3-4000: string builtin is not applicable to the provided type")
            if not isinstance(sep, str):
                raise EvaluationError("N3-4002: 'split' requires a string separator")
            return base.split(sep)
        if name == "join":
            if len(args) != 2:
                raise EvaluationError("N3-4001: 'join' requires a list of strings")
            items, sep = args
            if not isinstance(sep, str):
                raise EvaluationError("N3-4001: 'join' requires a list of strings")
            if not isinstance(items, list):
                raise EvaluationError("N3-4001: 'join' requires a list of strings")
            for item in items:
                if not isinstance(item, str):
                    raise EvaluationError("N3-4001: 'join' requires a list of strings")
            return sep.join(items)
        if name in {"minimum", "min", "maximum", "max", "mean", "average"}:
            if not args:
                raise EvaluationError("I expected a list of numbers for this aggregate, but nothing was provided.")
            seq = args[0]
            if not isinstance(seq, list):
                raise EvaluationError(f"I expected a list of numbers for {name}, but got {self._render_value(seq)} instead.")
            if not seq:
                if name in {"minimum", "min"}:
                    raise EvaluationError("I can't find a minimum on an empty list.")
                if name in {"maximum", "max"}:
                    raise EvaluationError("I can't find a maximum on an empty list.")
                raise EvaluationError("I can't compute mean of an empty list. If this list can be empty, guard it or provide a default.")
            nums = []
            for item in seq:
                nums.append(self._numeric_value(item, code="N3-4102"))
            try:
                if name in {"minimum", "min"}:
                    return min(nums)
                if name in {"maximum", "max"}:
                    return max(nums)
                return sum(nums) / len(nums)
            except Exception:
                raise EvaluationError("I couldn't compare these values to compute the aggregate.")
        if name == "round":
            if not args:
                raise EvaluationError("N3-4102: invalid type for numeric builtin")
            value = self._numeric_value(args[0], code="N3-4102")
            precision = 0
            if len(args) > 1:
                prec_val = args[1]
                if isinstance(prec_val, bool):
                    raise EvaluationError("N3-4101: invalid precision for 'round'")
                try:
                    precision = int(prec_val)
                except Exception:
                    raise EvaluationError("N3-4101: invalid precision for 'round'")
            return round(value, precision)
        if name in {"abs", "absolute"}:
            if not args:
                raise EvaluationError("N3-4102: invalid type for numeric builtin")
            val = self._numeric_value(args[0], code="N3-4102")
            return abs(val)
        if name == "append":
            if len(args) != 2:
                raise EvaluationError("append expects a list and a value.")
            seq = args[0]
            if not isinstance(seq, list):
                raise EvaluationError(f"I expected a list here for append, but got {self._render_value(seq)} instead.")
            return list(seq) + [args[1]]
        if name == "remove":
            if len(args) != 2:
                raise EvaluationError("remove expects a list and a value.")
            seq = args[0]
            if not isinstance(seq, list):
                raise EvaluationError(f"I expected a list here for remove, but got {self._render_value(seq)} instead.")
            target = args[1]
            result = list(seq)
            try:
                result.remove(target)
            except ValueError:
                # If the value isn't present, return the original list unchanged.
                return result
            return result
        if name == "insert":
            if len(args) != 3:
                raise EvaluationError("insert expects a list, an index, and a value.")
            seq = args[0]
            if not isinstance(seq, list):
                raise EvaluationError(f"I expected a list here for insert, but got {self._render_value(seq)} instead.")
            index_val = args[1]
            if isinstance(index_val, bool) or not isinstance(index_val, (int, float)):
                raise EvaluationError(
                    f"I expected a non-negative index within the list bounds for insert, but got {self._render_value(index_val)}."
                )
            if isinstance(index_val, float):
                if not index_val.is_integer():
                    raise EvaluationError(
                        f"I expected a non-negative index within the list bounds for insert, but got {self._render_value(index_val)}."
                    )
                index_val = int(index_val)
            if index_val < 0 or index_val > len(seq):
                raise EvaluationError(
                    f"I expected a non-negative index within the list bounds for insert, but got {self._render_value(index_val)}."
                )
            result = list(seq)
            result.insert(int(index_val), args[2])
            return result
        if name == "current_timestamp":
            if args:
                raise EvaluationError("N3-4305: builtin does not accept arguments")
            return datetime.now(timezone.utc).isoformat()
        if name == "current_date":
            if args:
                raise EvaluationError("N3-4305: builtin does not accept arguments")
            return datetime.now(timezone.utc).date().isoformat()
        if name == "random_uuid":
            if args:
                raise EvaluationError("N3-4305: builtin does not accept arguments")
            return str(uuid.uuid4())
        raise EvaluationError(f"N3-3200: unsupported builtin '{name}'")

    def _render_value(self, value: Any) -> str:
        try:
            rendered = repr(value)
        except Exception:
            rendered = f"<{value.__class__.__name__}>"
        if len(rendered) > 120:
            rendered = f"{rendered[:117]}..."
        return rendered

    def _resolve_path_value(self, value: Any, path: list[str]) -> Any:
        current = value
        for part in path:
            if isinstance(current, dict):
                if part in current:
                    current = current.get(part)
                else:
                    raise EvaluationError(
                        build_missing_field_error(part, current, context=f"I don't know field {part} on this record.")
                    )
            elif hasattr(current, part):
                current = getattr(current, part)
            else:
                raise EvaluationError(
                    f"N3-3300: I can only look up fields on a record, but got {self._render_value(current)} while looking for {part}."
                )
        return current

    def _ensure_boolean(self, value: Any, context: str) -> bool:
        if isinstance(value, bool):
            return value
        raise EvaluationError(
            f"I expected the condition in '{context}' to be true or false, but got {self._render_value(value)} instead."
        )

    def _ensure_collection(self, value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        raise EvaluationError(
            f"I expected a list or frame here, but got {type(value).__name__}. Collection pipelines only work on lists and frames."
        )

    def _with_row_binding(self, row: Any) -> tuple[bool, Any]:
        had_prev = self.env.has("row")
        prev_val = self.env.resolve("row") if had_prev else None
        if had_prev:
            self.env.assign("row", row)
        else:
            self.env.declare("row", row)
        return had_prev, prev_val

    def _restore_row_binding(self, had_prev: bool, prev_val: Any) -> None:
        if had_prev:
            self.env.assign("row", prev_val)
        else:
            self.env.remove("row")

    def _evaluate_group_expression(
        self, expr: ast_nodes.Expr | None, rows: list[Any], evaluator: "ExpressionEvaluator"
    ) -> Any:
        if expr is None:
            return None
        if isinstance(expr, ast_nodes.ListBuiltinCall):
            target = expr.expr
            if isinstance(target, ast_nodes.RecordFieldAccess) and isinstance(target.target, ast_nodes.Identifier):
                if target.target.name == "row":
                    values: list[Any] = []
                    for r in rows:
                        if not isinstance(r, dict):
                            raise EvaluationError(
                                f"N3-3300: I can only look up fields on a record, but got {self._render_value(r)} instead."
                            )
                        if target.field not in r:
                            raise EvaluationError(
                                build_missing_field_error(
                                    target.field,
                                    r,
                                    context=f"I don't know field {target.field} on this record.",
                                )
                            )
                        values.append(r.get(target.field))
                    return evaluator._dispatch_builtin((expr.name or "").lower(), [values])
            if isinstance(target, ast_nodes.VarRef) and target.root == "row" and target.path:
                values: list[Any] = []
                for r in rows:
                    current = r
                    for part in target.path:
                        if isinstance(current, dict) and part in current:
                            current = current.get(part)
                        elif hasattr(current, part):
                            current = getattr(current, part)
                        else:
                            raise EvaluationError(
                                build_missing_field_error(
                                    part,
                                    current,
                                    context=f"I don't know field {part} on this record.",
                                )
                            )
                    values.append(current)
                return evaluator._dispatch_builtin((expr.name or "").lower(), [values])
        return evaluator.evaluate(expr)

    def _eval_collection_pipeline(self, pipeline: IRCollectionPipeline) -> list[Any]:
        source_val = self.evaluate(pipeline.source) if pipeline.source is not None else None
        items = self._ensure_collection(source_val)
        for step in pipeline.steps:
            if isinstance(step, IRCollectionKeepRowsStep):
                kept: list[Any] = []
                for row in items:
                    had_prev, prev_val = self._with_row_binding(row)
                    try:
                        cond_val = self.evaluate(step.condition) if step.condition is not None else False
                        result = self._ensure_boolean(cond_val, "keep rows where ...")
                        if result:
                            kept.append(row)
                    finally:
                        self._restore_row_binding(had_prev, prev_val)
                items = kept
                continue
            if isinstance(step, IRCollectionDropRowsStep):
                kept: list[Any] = []
                for row in items:
                    had_prev, prev_val = self._with_row_binding(row)
                    try:
                        cond_val = self.evaluate(step.condition) if step.condition is not None else False
                        result = self._ensure_boolean(cond_val, "drop rows where ...")
                        if not result:
                            kept.append(row)
                    finally:
                        self._restore_row_binding(had_prev, prev_val)
                items = kept
                continue
            if isinstance(step, IRCollectionGroupByStep):
                groups: dict[Any, list[Any]] = {}
                for row in items:
                    had_prev, prev_val = self._with_row_binding(row)
                    try:
                        key_val = self.evaluate(step.key) if step.key is not None else None
                    finally:
                        self._restore_row_binding(had_prev, prev_val)
                    groups.setdefault(key_val, []).append(row)
                grouped_records: list[dict[str, Any]] = []
                for key_val, rows in groups.items():
                    group_env = self.env.clone()
                    if group_env.has("rows"):
                        group_env.assign("rows", rows)
                    else:
                        group_env.declare("rows", rows)
                    if group_env.has("group_key"):
                        group_env.assign("group_key", key_val)
                    else:
                        group_env.declare("group_key", key_val)
                    group_evaluator = ExpressionEvaluator(
                        group_env,
                        resolver=self.resolver,
                        rulegroup_resolver=self.rulegroup_resolver,
                        helper_resolver=self.helper_resolver,
                    )
                    record: dict[str, Any] = {"key": key_val}
                    for stmt in step.body:
                        if not isinstance(stmt, (ast_nodes.LetStatement, IRLet)):
                            raise EvaluationError("Only let statements are supported inside group by blocks for now.")
                        value = self._evaluate_group_expression(stmt.expr, rows, group_evaluator)
                        if group_env.has(stmt.name):
                            group_env.assign(stmt.name, value)
                        else:
                            group_env.declare(stmt.name, value, is_constant=stmt.is_constant)
                        record[stmt.name] = value
                    grouped_records.append(record)
                items = grouped_records
                continue
            if isinstance(step, IRCollectionSortStep):
                kind = step.kind
                direction = step.direction

                def sort_key(element: Any) -> Any:
                    env_clone = self.env.clone()
                    bind_name = "row" if kind == "rows" else "group"
                    if env_clone.has(bind_name):
                        env_clone.assign(bind_name, element)
                    else:
                        env_clone.declare(bind_name, element)
                    if kind == "groups":
                        if env_clone.has("row"):
                            env_clone.assign("row", element)
                        else:
                            env_clone.declare("row", element)
                        if isinstance(element, dict):
                            for k, v in element.items():
                                if env_clone.has(k):
                                    env_clone.assign(k, v)
                                else:
                                    env_clone.declare(k, v)
                    evaluator = ExpressionEvaluator(
                        env_clone,
                        resolver=self.resolver,
                        rulegroup_resolver=self.rulegroup_resolver,
                        helper_resolver=self.helper_resolver,
                    )
                    return evaluator.evaluate(step.key) if step.key is not None else None

                try:
                    items = sorted(items, key=sort_key, reverse=direction == "desc")
                except Exception:
                    raise EvaluationError("I couldn't sort these values because the sort keys are not comparable.")
                continue
            if isinstance(step, IRCollectionTakeStep):
                count_val = self.evaluate(step.count) if step.count is not None else 0
                if not isinstance(count_val, (int, float)) or isinstance(count_val, bool) or count_val < 0:
                    raise EvaluationError(
                        f"I expected a non-negative number for 'take first ...', but got {self._render_value(count_val)}."
                    )
                count_int = int(count_val)
                items = items[:count_int]
                continue
            if isinstance(step, IRCollectionSkipStep):
                count_val = self.evaluate(step.count) if step.count is not None else 0
                if not isinstance(count_val, (int, float)) or isinstance(count_val, bool) or count_val < 0:
                    raise EvaluationError(
                        f"I expected a non-negative number for 'skip first ...', but got {self._render_value(count_val)}."
                    )
                count_int = int(count_val)
                items = items[count_int:]
                continue
            raise EvaluationError(f"Unsupported collection pipeline step '{type(step).__name__}'")
        return items
