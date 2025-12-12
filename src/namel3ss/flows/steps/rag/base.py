from __future__ import annotations

import json
from typing import Any

from .... import ast_nodes
from ....errors import Namel3ssError
from ....runtime.expressions import ExpressionEvaluator
from ...graph import FlowRuntimeContext
from ...state.context import ExecutionContext

__all__ = ["FlowEngineRagBaseMixin"]


class FlowEngineRagBaseMixin:
    def _extract_cost(self, output: Any) -> float:
        if output is None:
            return 0.0
        if isinstance(output, dict):
            if "cost" in output and isinstance(output["cost"], (int, float)):
                return float(output["cost"])
            if "provider_result" in output:
                prov = output["provider_result"]
                if isinstance(prov, dict) and "cost" in prov:
                    try:
                        return float(prov["cost"])
                    except Exception:
                        return 0.0
        if hasattr(output, "cost"):
            try:
                return float(output.cost)
            except Exception:
                return 0.0
        return 0.0

    def _coerce_return_value(self, value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except Exception:
            try:
                return json.loads(json.dumps(value, default=str))
            except Exception:
                return str(value)

    async def _run_ai_stage(
        self,
        ai_name: str,
        payload: dict[str, Any],
        runtime_ctx: FlowRuntimeContext,
        step_name: str,
        flow_name: str,
        base_context: ExecutionContext,
    ) -> Any:
        ai_call = getattr(runtime_ctx.program, "ai_calls", {}).get(ai_name) if runtime_ctx else None
        if not ai_call:
            raise Namel3ssError(f"Stage '{step_name}' refers to AI '{ai_name}', but that AI is not declared.")
        try:
            return await self._call_ai_step(
                ai_call=ai_call,
                base_context=base_context,
                runtime_ctx=runtime_ctx,
                step_name=step_name,
                flow_name=flow_name,
                tools_mode=None,
            )
        except Exception:
            text_val = payload.get("question") or payload.get("context") if isinstance(payload, dict) else ""
            return text_val or f"{ai_name} output"

    def _evaluate_stage_number(self, expr: Any, evaluator: ExpressionEvaluator, default: int | None = None) -> int:
        if expr is None:
            return int(default or 0)
        if isinstance(expr, int):
            return expr
        if isinstance(expr, ast_nodes.Literal):
            try:
                return int(expr.value)
            except Exception:
                return int(default or 0)
        try:
            val = evaluator.evaluate(expr) if isinstance(expr, ast_nodes.Expr) else expr
            return int(val)
        except Exception:
            return int(default or 0)
