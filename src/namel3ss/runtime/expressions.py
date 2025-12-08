from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Tuple

from .. import ast_nodes
from ..errors import Namel3ssError


class EvaluationError(Namel3ssError):
    """Raised when expression evaluation fails."""


UNDEFINED = object()


class VariableEnvironment:
    """Per-run variable environment."""

    def __init__(self, backing: dict[str, Any] | None = None) -> None:
        self.values: dict[str, Any] = backing if backing is not None else {}
        self._declared: set[str] = set(self.values.keys())

    def has(self, name: str) -> bool:
        return name in self._declared

    def declare(self, name: str, value: Any) -> None:
        if name in self._declared:
            raise EvaluationError(f"Variable '{name}' is already defined")
        self._declared.add(name)
        self.values[name] = value

    def assign(self, name: str, value: Any) -> None:
        if name not in self._declared:
            raise EvaluationError(f"Variable '{name}' is not defined")
        self.values[name] = value

    def remove(self, name: str) -> None:
        self._declared.discard(name)
        self.values.pop(name, None)

    def resolve(self, name: str) -> Any:
        if name in self._declared:
            return self.values[name]
        raise EvaluationError(f"Variable '{name}' is not defined")

    def clone(self) -> "VariableEnvironment":
        return VariableEnvironment(dict(self.values))


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

    def evaluate(self, expr: ast_nodes.Expr) -> Any:
        if isinstance(expr, ast_nodes.Literal):
            return expr.value
        if isinstance(expr, ast_nodes.VarRef):
            dotted = expr.root if not expr.path else ".".join([expr.root] + expr.path)
            # Allow env values (e.g., loop/local) to be resolved directly
            if self.env.has(dotted):
                return self.env.resolve(dotted)
            try:
                # Prefer exact env hit on root if present (locals/loop vars stored bare)
                if self.env.has(expr.root) and not expr.path:
                    return self.env.resolve(expr.root)
            except Exception:
                pass
            found, value = self.resolver(dotted)
            if found:
                return value
            raise EvaluationError(f"Variable '{dotted}' is not defined")
        if isinstance(expr, ast_nodes.Identifier):
            if self.env.has(expr.name):
                return self.env.resolve(expr.name)
            if "." in expr.name:
                parts = expr.name.split(".")
                base = parts[0]
                if self.env.has(base):
                    value: Any = self.env.resolve(base)
                    for part in parts[1:]:
                        if isinstance(value, dict) and part in value:
                            value = value.get(part)
                        elif hasattr(value, part):
                            value = getattr(value, part)
                        else:
                            raise EvaluationError("N3-3300: unknown record field")
                    return value
            # Support dotted lookups via resolver
            found, value = self.resolver(expr.name)
            if not found:
                raise EvaluationError(f"Variable '{expr.name}' is not defined")
            return value
        if isinstance(expr, ast_nodes.RecordFieldAccess):
            target = self.evaluate(expr.target) if expr.target else None
            if not isinstance(target, dict):
                raise EvaluationError("N3-3300: unknown record field access")
            if expr.field not in target:
                raise EvaluationError("N3-3300: unknown record field")
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
        if isinstance(expr, ast_nodes.FilterExpression):
            source = self.evaluate(expr.source) if expr.source else None
            if not isinstance(source, list):
                raise EvaluationError("N3-3400: for-each/filter requires a list value")
            result: list[Any] = []
            for item in source:
                had_prev = self.env.has(expr.var_name)
                prev_val = self.env.resolve(expr.var_name) if had_prev else None
                if had_prev:
                    self.env.assign(expr.var_name, item)
                else:
                    self.env.declare(expr.var_name, item)
                try:
                    pred_val = self.evaluate(expr.predicate) if expr.predicate else False
                    if not isinstance(pred_val, bool):
                        raise EvaluationError("N3-3201: filter predicate must yield boolean")
                    if pred_val:
                        result.append(item)
                finally:
                    if had_prev:
                        self.env.assign(expr.var_name, prev_val)
                    else:
                        self.env.remove(expr.var_name)
            return result
        if isinstance(expr, ast_nodes.MapExpression):
            source = self.evaluate(expr.source) if expr.source else None
            if not isinstance(source, list):
                raise EvaluationError("N3-3400: map requires a list value")
            mapped: list[Any] = []
            for item in source:
                had_prev = self.env.has(expr.var_name)
                prev_val = self.env.resolve(expr.var_name) if had_prev else None
                if had_prev:
                    self.env.assign(expr.var_name, item)
                else:
                    self.env.declare(expr.var_name, item)
                try:
                    mapped.append(self.evaluate(expr.mapper) if expr.mapper else item)
                finally:
                    if had_prev:
                        self.env.assign(expr.var_name, prev_val)
                    else:
                        self.env.remove(expr.var_name)
            return mapped
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
        if name in {"length"}:
            arg = args[0] if args else None
            if not isinstance(arg, list):
                raise EvaluationError("N3-3200: length requires a list")
            return len(arg)
        if name in {"first"}:
            arg = args[0] if args else None
            if not isinstance(arg, list):
                raise EvaluationError("N3-3200: first requires a list")
            if not arg:
                raise EvaluationError("N3-3200: first requires a non-empty list")
            return arg[0]
        if name in {"last"}:
            arg = args[0] if args else None
            if not isinstance(arg, list):
                raise EvaluationError("N3-3200: last requires a list")
            if not arg:
                raise EvaluationError("N3-3200: last requires a non-empty list")
            return arg[-1]
        if name in {"reverse"}:
            arg = args[0] if args else None
            if not isinstance(arg, list):
                raise EvaluationError("N3-3200: reverse requires a list")
            return list(reversed(arg))
        if name in {"unique"}:
            arg = args[0] if args else None
            if not isinstance(arg, list):
                raise EvaluationError("N3-3200: unique requires a list")
            seen = set()
            unique_items = []
            for item in arg:
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
            if not isinstance(arg, list):
                raise EvaluationError("N3-3200: sorted requires a list")
            try:
                return sorted(arg)
            except Exception:
                raise EvaluationError("N3-3204: cannot compare elements for sorting")
        if name in {"sum"}:
            arg = args[0] if args else None
            if not isinstance(arg, list):
                raise EvaluationError("N3-3200: sum requires a list")
            total = 0
            for item in arg:
                num = self._to_number(item)
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
                raise EvaluationError("N3-4100: aggregate requires a non-empty numeric list")
            seq = args[0]
            if not isinstance(seq, list) or not seq:
                raise EvaluationError("N3-4100: aggregate requires a non-empty numeric list")
            nums = [self._numeric_value(item, code="N3-4102") for item in seq]
            if name in {"minimum", "min"}:
                return min(nums)
            if name in {"maximum", "max"}:
                return max(nums)
            return sum(nums) / len(nums)
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
