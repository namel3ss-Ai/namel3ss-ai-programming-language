from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Any, Dict, List

from .. import ast_nodes
from ..errors import Namel3ssError
from .expressions import EvaluationError, ExpressionEvaluator, VariableEnvironment


@dataclass
class FrameSpec:
    name: str
    path: str | None = None
    delimiter: str | None = None
    has_headers: bool = False
    select_cols: list[str] | None = None
    where: ast_nodes.Expr | None = None


class FrameRegistry:
    """Runtime registry for frames; loads lazily and caches per registry."""

    def __init__(self, frames: Dict[str, Any] | None = None) -> None:
        self.frames = frames or {}
        self._cache: Dict[str, List[Any]] = {}
        self._store: Dict[str, List[dict]] = {}

    def register(self, name: str, spec: Any) -> None:
        self.frames[name] = spec

    def get_rows(self, name: str) -> List[Any]:
        if name not in self.frames:
            raise Namel3ssError("N3F-1100: frame not defined")
        frame = self.frames[name]
        backend = getattr(frame, "backend", None) or ("file" if getattr(frame, "path", None) else "memory")
        if backend != "file":
            # Memory-backed frames live in the in-memory store and should reflect current values.
            return list(self._store.get(name, []))
        if name in self._cache:
            return self._cache[name]
        rows = self._load_frame(frame)
        self._cache[name] = rows
        return rows

    def _load_frame(self, frame: Any) -> List[Any]:
        path = getattr(frame, "path", None)
        if not path:
            raise Namel3ssError("N3F-1000: frame source missing")
        delimiter = getattr(frame, "delimiter", None) or ","
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                if getattr(frame, "has_headers", False):
                    reader = csv.DictReader(fh, delimiter=delimiter)
                    headers = reader.fieldnames or []
                    select_cols = getattr(frame, "select_cols", None) or []
                    if select_cols:
                        for col in select_cols:
                            if col not in headers:
                                raise Namel3ssError("N3F-1002: unknown column in select")
                    rows: list[dict] = []
                    for raw in reader:
                        row = {k: self._coerce_value(v) for k, v in (raw or {}).items()}
                        if getattr(frame, "where", None) is not None:
                            if not self._eval_where(frame.where, row):
                                continue
                        if select_cols:
                            row = {col: row.get(col) for col in select_cols}
                        rows.append(row)
                    return rows
                else:
                    rows: list[list[Any]] = []
                    reader = csv.reader(fh, delimiter=delimiter)
                    for raw in reader:
                        values = [self._coerce_value(v) for v in raw]
                        if getattr(frame, "select_cols", None):
                            raise Namel3ssError("N3F-1001: select requires headers")
                        if getattr(frame, "where", None) is not None:
                            raise Namel3ssError("N3F-1001: where requires headers")
                        rows.append(values)
                    return rows
        except Namel3ssError:
            raise
        except FileNotFoundError as exc:  # pragma: no cover - safety
            raise Namel3ssError("N3F-1100: frame source file not found") from exc
        except Exception as exc:  # pragma: no cover - safety
            raise Namel3ssError("N3F-1100: frame could not be loaded") from exc

    def insert(self, name: str, row: dict) -> None:
        frame = self.frames.get(name)
        if not frame:
            raise Namel3ssError(f"N3L-830: Frame '{name}' is not declared.")
        backend = getattr(frame, "backend", None)
        if not backend:
            # fallback to in-memory if no backend but still allow basic persistence
            backend = "memory"
        self._store.setdefault(name, []).append(dict(row))

    def query(self, name: str, filters: dict | None = None) -> list[dict]:
        frame = self.frames.get(name)
        if not frame:
            raise Namel3ssError(f"N3L-830: Frame '{name}' is not declared.")
        backend = getattr(frame, "backend", None) or ("file" if getattr(frame, "path", None) else "memory")
        conditions = self._normalize_conditions(filters)
        if backend == "file":
            rows = self.get_rows(name)
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                return [r for r in rows if self._row_matches(r, conditions)]
            return rows
        data = self._store.get(name, [])
        return [r for r in data if self._row_matches(r, conditions)]

    def update(self, name: str, filters: dict | None, updates: dict) -> int:
        frame = self.frames.get(name)
        if not frame:
            raise Namel3ssError(f"N3L-830: Frame '{name}' is not declared.")
        data = self._store.setdefault(name, [])
        conditions = self._normalize_conditions(filters)
        count = 0
        for row in data:
            if self._row_matches(row, conditions):
                row.update(updates)
                count += 1
        return count

    def delete(self, name: str, filters: dict | None) -> int:
        frame = self.frames.get(name)
        if not frame:
            raise Namel3ssError(f"N3L-830: Frame '{name}' is not declared.")
        data = self._store.setdefault(name, [])
        conditions = self._normalize_conditions(filters)
        remain: list[dict] = []
        deleted = 0
        for row in data:
            if self._row_matches(row, conditions):
                deleted += 1
                continue
            remain.append(row)
        self._store[name] = remain
        return deleted

    def _eval_where(self, expr: ast_nodes.Expr, row: dict) -> bool:
        env = VariableEnvironment(dict(row))
        evaluator = ExpressionEvaluator(env, resolver=lambda name: (True, row.get(name)))
        try:
            val = evaluator.evaluate(expr)
        except EvaluationError as exc:
            raise Namel3ssError(str(exc))
        if not isinstance(val, bool):
            raise Namel3ssError("N3F-1003: where clause must be boolean")
        return bool(val)

    def _coerce_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "":
                return ""
            try:
                if "." in stripped:
                    f_val = float(stripped)
                    i_val = int(f_val)
                    return i_val if f_val == i_val else f_val
                return int(stripped)
            except Exception:
                return stripped
        return value

    def _normalize_conditions(self, filters: dict | list | None) -> list[dict]:
        if not filters:
            return []
        if isinstance(filters, dict) and filters.get("type") in {"leaf", "and", "or", "all", "any"}:
            return [filters]
        if isinstance(filters, dict):
            return [{"field": k, "op": "eq", "value": v} for k, v in filters.items()]
        return list(filters)

    def _row_matches(self, row: dict, conditions: list[dict]) -> bool:
        def _ensure_bool(val: Any) -> bool:
            if isinstance(val, bool):
                return val
            raise Namel3ssError("Where clause must evaluate to a boolean.")

        def _eval(node: dict | list | None) -> bool:
            if node is None:
                return True
            if isinstance(node, list):
                for item in node:
                    if not _eval(item):
                        return False
                return True
            if not isinstance(node, dict):
                raise Namel3ssError("Where clause must evaluate to a boolean.")
            ntype = node.get("type")
            if ntype in {"and", "or", "all", "any"}:
                if ntype == "and":
                    return _eval(node.get("left")) and _eval(node.get("right"))
                if ntype == "or":
                    return _eval(node.get("left")) or _eval(node.get("right"))
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
            field = node.get("field")
            op = node.get("op")
            value = node.get("value")
            present = field in row
            row_val = row.get(field)
            try:
                if op == "eq":
                    ok = row_val == value
                elif op == "neq":
                    ok = row_val != value
                elif op == "gt":
                    ok = row_val > value
                elif op == "lt":
                    ok = row_val < value
                elif op == "ge":
                    ok = row_val >= value
                elif op == "le":
                    ok = row_val <= value
                elif op == "in":
                    if not isinstance(value, (list, tuple, set)):
                        raise Namel3ssError("Filters using 'is one of' must compare against a list of values.")
                    ok = row_val in value
                elif op == "is_null":
                    ok = (not present) or row_val is None
                elif op == "is_not_null":
                    ok = present and row_val is not None
                else:  # pragma: no cover - defensive
                    ok = False
            except Exception as exc:
                raise Namel3ssError(
                    f"I couldn't apply this filter on field '{field}' because the values are not comparable."
                ) from exc
            return _ensure_bool(ok)

        for cond in conditions:
            if not _eval(cond):
                return False
        return True
