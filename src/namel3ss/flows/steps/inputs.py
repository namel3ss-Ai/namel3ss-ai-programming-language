from __future__ import annotations

import time
from typing import Any

from ... import ast_nodes
from ...runtime.expressions import ExpressionEvaluator, VariableEnvironment
from ..graph import FlowRuntimeContext, FlowState

__all__ = ["FlowEngineInputMixin"]


class FlowEngineInputMixin:
    def _resolve_provided_input(self, name: str, runtime_ctx: FlowRuntimeContext, state: FlowState) -> Any:
        env = state.variables or VariableEnvironment()
        if env.has(name):
            try:
                return env.resolve(name)
            except Exception:
                return None
        ctx_inputs = {}
        exec_ctx = getattr(runtime_ctx, "execution_context", None)
        if exec_ctx and isinstance(getattr(exec_ctx, "metadata", None), dict):
            ctx_inputs = exec_ctx.metadata.get("inputs", {}) or {}
        if isinstance(ctx_inputs, dict) and name in ctx_inputs:
            return ctx_inputs.get(name)
        return None

    def _assign_variable(self, name: str, value: Any, state: FlowState) -> None:
        env = state.variables or VariableEnvironment()
        if env.has(name):
            env.assign(name, value)
        else:
            env.declare(name, value)
        state.variables = env
        state.set(name, value)

    def _validation_to_dict(self, validation: ast_nodes.InputValidation | None, evaluator: ExpressionEvaluator) -> dict | None:
        if not validation:
            return None
        data: dict[str, Any] = {}
        if validation.field_type:
            data["type"] = validation.field_type
        if validation.min_expr is not None:
            try:
                data["min"] = evaluator.evaluate(validation.min_expr)
            except Exception:
                data["min"] = None
        if validation.max_expr is not None:
            try:
                data["max"] = evaluator.evaluate(validation.max_expr)
            except Exception:
                data["max"] = None
        return data or None

    def _build_log_entry(self, level: str, message: str, metadata: Any, state: FlowState) -> dict:
        return {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "metadata": metadata,
        }

    def _build_note_entry(self, message: str, state: FlowState) -> dict:
        return {"timestamp": time.time(), "message": message}

    def _build_checkpoint_entry(self, label: str, state: FlowState) -> dict:
        return {"timestamp": time.time(), "label": label}
