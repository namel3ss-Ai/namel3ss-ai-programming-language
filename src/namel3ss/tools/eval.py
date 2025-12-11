"""
Tool evaluation runner.

Executes a declared tool against rows from a dataset frame, computing simple metrics
like success_rate, error_rate, and average latency.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..errors import Namel3ssError
from ..flows.graph import FlowNode, FlowState
from ..runtime.context import ExecutionContext
from ..obs.tracer import Tracer


@dataclass
class ToolEvaluationRow:
    inputs: Dict[str, Any]
    result: Any
    success: bool
    latency_ms: float
    status: int | None = None
    error: str | None = None


@dataclass
class ToolEvaluationResult:
    name: str
    tool: str
    dataset_frame: str
    metrics: Dict[str, float] = field(default_factory=dict)
    rows: List[ToolEvaluationRow] = field(default_factory=list)
    num_rows: int = 0


def _stringify_data(data: Any) -> str:
    if data is None:
        return ""
    if isinstance(data, (dict, list)):
        try:
            return json.dumps(data)
        except Exception:
            return str(data)
    return str(data)


def _compute_success(result: dict, expected_status: Any, expected_body_substring: str | None) -> bool:
    ok = bool(result.get("ok"))
    if expected_status is not None:
        ok = ok and result.get("status") == expected_status
    if expected_body_substring:
        ok = ok and (expected_body_substring in _stringify_data(result.get("data")))
    return ok


async def _run_single_tool(flow_engine, runtime_ctx, tool_name: str, args: dict[str, Any]) -> dict:
    node = FlowNode(
        id=f"tool_eval:{tool_name}",
        kind="tool",
        config={"target": tool_name, "params": {"input": args}},
        next_ids=[],
    )
    state = FlowState(context={"flow_name": f"tool_eval:{tool_name}"})
    return await flow_engine._execute_tool_call(node, state, runtime_ctx)


def run_tool_evaluation(program, eval_cfg, flow_engine, limit: Optional[int] = None) -> ToolEvaluationResult:
    async def _run() -> ToolEvaluationResult:
        frame_registry = getattr(flow_engine, "frame_registry", None)
        if not frame_registry:
            raise Namel3ssError("Frame registry is not available for tool evaluation.")
        rows_data = frame_registry.get_rows(eval_cfg.dataset_frame)
        if limit is not None:
            try:
                lim = int(limit)
            except Exception:
                lim = None
            if lim is not None and lim >= 0:
                rows_data = rows_data[:lim]

        base_context = ExecutionContext(
            app_name="tool_evaluation",
            request_id=str(uuid4()),
            tracer=Tracer(),
            metrics=getattr(flow_engine, "metrics", None),
            secrets=getattr(flow_engine, "secrets", None),
        )
        runtime_ctx = flow_engine._build_runtime_context(base_context)
        rows: list[ToolEvaluationRow] = []
        success_count = 0
        error_count = 0
        latency_sum = 0.0

        for row in rows_data:
            if not isinstance(row, dict):
                raise Namel3ssError("Dataset rows for tool evaluation must be records with column names.")
            inputs = {}
            for param, col in (eval_cfg.input_mapping or {}).items():
                inputs[param] = row.get(col)
            expected_status = row.get(eval_cfg.expected_status_column) if eval_cfg.expected_status_column else None
            expected_body = row.get(eval_cfg.expected_body_column) if eval_cfg.expected_body_column else None
            start = time.perf_counter()
            try:
                result = await _run_single_tool(flow_engine, runtime_ctx, eval_cfg.tool, inputs)
            except Exception as exc:
                latency_ms = (time.perf_counter() - start) * 1000.0
                error_count += 1
                rows.append(
                    ToolEvaluationRow(
                        inputs=inputs,
                        result=None,
                        success=False,
                        latency_ms=latency_ms,
                        error=str(exc),
                    )
                )
                latency_sum += latency_ms
                continue
            latency_ms = (time.perf_counter() - start) * 1000.0
            success = _compute_success(result or {}, expected_status, str(expected_body) if expected_body is not None else None)
            if success:
                success_count += 1
            if not result.get("ok"):
                error_count += 1
            latency_sum += latency_ms
            rows.append(
                ToolEvaluationRow(
                    inputs=inputs,
                    result=result,
                    success=success,
                    latency_ms=latency_ms,
                    status=result.get("status") if isinstance(result, dict) else None,
                    error=result.get("error") if isinstance(result, dict) else None,
                )
            )

        total = len(rows) if rows else 1
        metrics: dict[str, float] = {}
        metric_names = [m.lower() for m in (eval_cfg.metrics or [])]
        if "success_rate" in metric_names:
            metrics["success_rate"] = success_count / total
        if "error_rate" in metric_names:
            metrics["error_rate"] = error_count / total
        if "latency_ms" in metric_names:
            metrics["latency_ms"] = latency_sum / total

        return ToolEvaluationResult(
            name=eval_cfg.name,
            tool=eval_cfg.tool,
            dataset_frame=eval_cfg.dataset_frame,
            metrics=metrics,
            rows=rows,
            num_rows=len(rows),
        )

    return asyncio.run(_run())


def run_tool_evaluation_by_name(program, flow_engine, evaluation_name: str, limit: Optional[int] = None) -> ToolEvaluationResult:
    eval_cfg = getattr(program, "tool_evaluations", {}).get(evaluation_name)
    if not eval_cfg:
        raise Namel3ssError(f"Tool evaluation '{evaluation_name}' is not declared.")
    return run_tool_evaluation(program, eval_cfg, flow_engine, limit=limit)
