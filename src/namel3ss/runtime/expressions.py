from __future__ import annotations

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
    ) -> None:
        self.env = env
        self.resolver = resolver
        self.rulegroup_resolver = rulegroup_resolver

    def evaluate(self, expr: ast_nodes.Expr) -> Any:
        if isinstance(expr, ast_nodes.Literal):
            return expr.value
        if isinstance(expr, ast_nodes.Identifier):
            if self.env.has(expr.name):
                return self.env.resolve(expr.name)
            found, value = self.resolver(expr.name)
            if not found:
                raise EvaluationError(f"Variable '{expr.name}' is not defined")
            return value
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
        raise EvaluationError("Unsupported expression")

    def _to_number(self, value: Any) -> float | int:
        if isinstance(value, bool):
            raise EvaluationError("Arithmetic on non-numeric values")
        if isinstance(value, (int, float)):
            return value
        raise EvaluationError("Arithmetic on non-numeric values")

    def _numeric_unary(self, value: Any, sign: int) -> float | int:
        num = self._to_number(value)
        return num if sign > 0 else -num
