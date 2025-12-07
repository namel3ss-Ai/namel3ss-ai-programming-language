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
        if name in self._cache:
            return self._cache[name]
        if name not in self.frames:
            raise Namel3ssError("N3F-1100: frame not defined")
        frame = self.frames[name]
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
        filters = filters or {}
        if backend == "file":
            rows = self.get_rows(name)
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                return [
                    r for r in rows if all(r.get(k) == v for k, v in filters.items())
                ]
            return rows
        data = self._store.get(name, [])
        return [r for r in data if all(r.get(k) == v for k, v in filters.items())]

    def update(self, name: str, filters: dict | None, updates: dict) -> int:
        frame = self.frames.get(name)
        if not frame:
            raise Namel3ssError(f"N3L-830: Frame '{name}' is not declared.")
        data = self._store.setdefault(name, [])
        filters = filters or {}
        count = 0
        for row in data:
            if all(row.get(k) == v for k, v in filters.items()):
                row.update(updates)
                count += 1
        return count

    def delete(self, name: str, filters: dict | None) -> int:
        frame = self.frames.get(name)
        if not frame:
            raise Namel3ssError(f"N3L-830: Frame '{name}' is not declared.")
        data = self._store.setdefault(name, [])
        filters = filters or {}
        remain: list[dict] = []
        deleted = 0
        for row in data:
            if all(row.get(k) == v for k, v in filters.items()):
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
