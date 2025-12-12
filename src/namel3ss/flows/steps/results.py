from __future__ import annotations

from typing import Any

from ... import ast_nodes
from ...errors import Namel3ssError
from ...runtime.expressions import ExpressionEvaluator, VariableEnvironment
from ..graph import FlowState
from ...ir import IRMatchBranch

__all__ = ["FlowEngineResultMixin"]


class FlowEngineResultMixin:
    def _is_error_result(self, value: Any) -> bool:
        res = self._normalize_result(value)
        return bool(res) and res.get("ok") is False

    def _is_success_result(self, value: Any) -> bool:
        res = self._normalize_result(value)
        return bool(res) and res.get("ok") is True

    def _normalize_result(self, value: Any) -> dict[str, Any] | None:
        if isinstance(value, Exception):
            return {"ok": False, "value": None, "error": value, "raw": value}
        mapping: dict[str, Any] | None = None
        if isinstance(value, dict):
            mapping = value
        else:
            attrs: dict[str, Any] = {}
            for key in ("ok", "success", "error", "data", "result", "value", "final_output", "final_answer"):
                if hasattr(value, key):
                    try:
                        attrs[key] = getattr(value, key)
                    except Exception:
                        continue
            mapping = attrs or None
        if mapping is None:
            return None
        has_signal = any(k in mapping for k in ("ok", "success", "error", "data", "result", "value"))
        if not has_signal:
            return None
        ok_val = mapping.get("ok", None)
        if ok_val is None and "success" in mapping:
            ok_val = mapping.get("success")
        error_val = mapping.get("error", None)
        payload = None
        for key in ("data", "result", "value", "final_output", "final_answer"):
            if key in mapping:
                payload = mapping.get(key)
                break
        if ok_val is None and error_val is not None:
            ok_val = False
        if ok_val is None and payload is not None:
            ok_val = True
        if ok_val is None:
            return None
        return {"ok": bool(ok_val), "value": payload, "error": error_val, "raw": value}

    def _extract_success_payload(self, value: Any) -> Any:
        res = self._normalize_result(value)
        if res is None:
            return value
        if res.get("value") is not None:
            return res.get("value")
        return res.get("raw")

    def _extract_error_payload(self, value: Any) -> Any:
        res = self._normalize_result(value)
        if res is None:
            return value
        if res.get("error") is not None:
            return res.get("error")
        return res.get("raw")

    def _match_branch(self, br: IRMatchBranch, target_val: Any, evaluator: ExpressionEvaluator, state: FlowState, normalized_result: dict[str, Any] | None = None) -> bool:
        pattern = br.pattern
        env = state.variables or VariableEnvironment()
        result_info = normalized_result if normalized_result is not None else self._normalize_result(target_val)
        if isinstance(pattern, ast_nodes.SuccessPattern):
            if not result_info or result_info.get("ok") is not True:
                return False
            payload = result_info.get("value") if result_info is not None else None
            if payload is None and result_info is not None:
                payload = result_info.get("raw")
            if pattern.binding:
                if env.has(pattern.binding):
                    env.assign(pattern.binding, payload)
                else:
                    env.declare(pattern.binding, payload)
                state.set(pattern.binding, payload)
            return True
        if isinstance(pattern, ast_nodes.ErrorPattern):
            if not result_info or result_info.get("ok") is True:
                return False
            payload = result_info.get("error") if result_info is not None else None
            if payload is None and result_info is not None:
                payload = result_info.get("raw")
            if pattern.binding:
                if env.has(pattern.binding):
                    env.assign(pattern.binding, payload)
                else:
                    env.declare(pattern.binding, payload)
                state.set(pattern.binding, payload)
            return True
        if pattern is None:
            return True
        try:
            pat_val = evaluator.evaluate(pattern)
        except Exception as exc:
            raise Namel3ssError(str(exc))
        if isinstance(pat_val, bool):
            return isinstance(target_val, bool) and target_val is pat_val
        return target_val == pat_val
