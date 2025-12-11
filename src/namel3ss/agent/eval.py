"""
Agent evaluation runner.

Executes a declared agent against rows from a dataset frame, computing metrics
like answer_correctness, latency, error_rate, and tool usage correctness.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..errors import Namel3ssError
from ..obs.tracer import Tracer
from ..runtime.context import ExecutionContext


@dataclass
class AgentEvaluationRow:
    inputs: Dict[str, Any]
    answer: Any
    expected_answer: Any | None
    success: bool
    latency_seconds: float
    error: str | None = None
    metrics: Dict[str, float | None] = field(default_factory=dict)
    tools_used: list[str] | None = None


@dataclass
class AgentEvaluationResult:
    name: str
    agent: str
    dataset_frame: str
    metrics: Dict[str, float] = field(default_factory=dict)
    rows: List[AgentEvaluationRow] = field(default_factory=list)
    num_rows: int = 0


def _normalize_result(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Exception):
        return {"ok": False, "value": None, "error": value, "raw": value}
    mapping: dict[str, Any] | None = None
    if isinstance(value, dict):
        mapping = value
    else:
        attrs: dict[str, Any] = {}
        for key in ("ok", "success", "error", "data", "result", "value", "final_answer", "final_output"):
            if hasattr(value, key):
                try:
                    attrs[key] = getattr(value, key)
                except Exception:
                    continue
        mapping = attrs or None
    if mapping is None:
        return None
    has_signal = any(k in mapping for k in ("ok", "success", "error", "data", "result", "value", "final_answer", "final_output"))
    if not has_signal:
        return None
    ok_val = mapping.get("ok", None)
    if ok_val is None and "success" in mapping:
        ok_val = mapping.get("success")
    error_val = mapping.get("error", None)
    payload = None
    for key in ("data", "result", "value", "final_answer", "final_output"):
        if key in mapping:
            payload = mapping.get(key)
            if payload is not None:
                break
    if ok_val is None and error_val is not None:
        ok_val = False
    if ok_val is None and payload is not None:
        ok_val = True
    if ok_val is None:
        return None
    return {"ok": bool(ok_val), "value": payload, "error": error_val, "raw": value}


def _compute_answer_match(answer: Any, expected: Any, allow_llm_judge: bool = False) -> float:
    if expected is None:
        return 1.0 if answer not in (None, "") else 0.0
    answer_text = "" if answer is None else str(answer).strip()
    expected_text = str(expected).strip()
    if not allow_llm_judge:
        return 1.0 if answer_text.lower() == expected_text.lower() else 0.0
    # Lightweight heuristic for judge: substring containment as a stand-in for LLM judging
    if expected_text and expected_text.lower() in answer_text.lower():
        return 1.0
    if answer_text and answer_text.lower() in expected_text.lower():
        return 1.0
    return 0.0


def _compute_tool_usage(tools_used: list[str] | None, expected: Any) -> float | None:
    if expected is None:
        return None if not tools_used else 1.0
    expected_list: list[str] = []
    if isinstance(expected, (list, tuple)):
        expected_list = [str(x) for x in expected]
    else:
        expected_list = [t.strip() for t in str(expected).split(",") if t.strip()]
    if not expected_list:
        return None
    used = set(str(t) for t in (tools_used or []))
    exp = set(expected_list)
    if not exp:
        return None
    return 1.0 if exp.issubset(used) else 0.0


async def _run_single_agent(flow_engine, eval_cfg, row: dict[str, Any], base_context: ExecutionContext):
    ctx = ExecutionContext(
        app_name=base_context.app_name,
        request_id=str(uuid4()),
        tracer=base_context.tracer,
        metrics=base_context.metrics,
        secrets=base_context.secrets,
        tool_registry=getattr(flow_engine, "tool_registry", None),
    )
    ctx.metadata = {"agent_evaluation_row": row}
    ctx.variables = {}
    for param, col in (eval_cfg.input_mapping or {}).items():
        ctx.variables[param] = row.get(col)
        if param in {"question", "prompt", "query"} and ctx.user_input is None:
            ctx.user_input = row.get(col)
    if ctx.user_input is None and ctx.variables:
        # Pick the first variable as user_input fallback to make basic prompts work.
        ctx.user_input = next(iter(ctx.variables.values()))
    start = time.perf_counter()
    result = await asyncio.to_thread(flow_engine.agent_runner.run, eval_cfg.agent, ctx)
    latency = time.perf_counter() - start
    normalized = _normalize_result(result) or {}
    answer_val = normalized.get("value")
    if answer_val is None and hasattr(result, "final_answer"):
        answer_val = getattr(result, "final_answer")
    if hasattr(answer_val, "text"):
        try:
            answer_val = getattr(answer_val, "text")
        except Exception:
            pass
    if isinstance(answer_val, dict) and "text" in answer_val:
        answer_val = answer_val.get("text")
    return {
        "result": result,
        "normalized": normalized,
        "answer": answer_val,
        "latency_seconds": latency,
        "tools_used": ctx.metadata.get("tools_used") if isinstance(ctx.metadata, dict) else None,
    }


def run_agent_evaluation(program, eval_cfg, flow_engine, limit: Optional[int] = None) -> AgentEvaluationResult:
    async def _run() -> AgentEvaluationResult:
        frame_registry = getattr(flow_engine, "frame_registry", None)
        if not frame_registry:
            raise Namel3ssError("Frame registry is not available for agent evaluation.")
        rows_data = frame_registry.get_rows(eval_cfg.dataset_frame)
        if limit is not None:
            try:
                lim = int(limit)
            except Exception:
                lim = None
            if lim is not None and lim >= 0:
                rows_data = rows_data[:lim]

        base_context = ExecutionContext(
            app_name="agent_evaluation",
            request_id=str(uuid4()),
            tracer=Tracer(),
            metrics=getattr(flow_engine, "metrics", None),
            secrets=getattr(flow_engine, "secrets", None),
            tool_registry=getattr(flow_engine, "tool_registry", None),
        )

        rows: list[AgentEvaluationRow] = []
        success_count = 0
        error_count = 0
        latency_sum = 0.0
        metric_names = [m.lower() for m in (eval_cfg.metrics or [])]

        for row in rows_data:
            if not isinstance(row, dict):
                raise Namel3ssError("Dataset rows for agent evaluation must be records with column names.")
            inputs = {}
            for param, col in (eval_cfg.input_mapping or {}).items():
                inputs[param] = row.get(col)
            expected_answer = row.get(eval_cfg.expected_answer_column) if eval_cfg.expected_answer_column else None
            expected_tools = row.get(eval_cfg.expected_tool_column) if getattr(eval_cfg, "expected_tool_column", None) else None
            error: str | None = None
            single_result: dict[str, Any] | None = None
            try:
                single_result = await _run_single_agent(flow_engine, eval_cfg, row, base_context)
            except Exception as exc:
                error = str(exc)
                error_count += 1
                rows.append(
                    AgentEvaluationRow(
                        inputs=inputs,
                        answer=None,
                        expected_answer=expected_answer,
                        success=False,
                        latency_seconds=0.0,
                        error=error,
                        metrics={},
                        tools_used=None,
                    )
                )
                continue
            result_payload = single_result or {}
            normalized = result_payload.get("normalized") or {}
            answer_val = result_payload.get("answer")
            latency = float(result_payload.get("latency_seconds") or 0.0)
            latency_sum += latency
            is_ok = normalized.get("ok", True)
            if not is_ok:
                error_count += 1
            score = _compute_answer_match(answer_val, expected_answer, getattr(eval_cfg, "allow_llm_judge", False))
            success = bool(score >= 0.5)
            if success:
                success_count += 1
            metric_values: dict[str, float | None] = {}
            if "answer_correctness" in metric_names:
                metric_values["answer_correctness"] = score
            if "latency_seconds" in metric_names:
                metric_values["latency_seconds"] = latency
            if "error_rate" in metric_names:
                metric_values["error_rate"] = 0.0 if is_ok else 1.0
            if "tool_usage_correctness" in metric_names:
                metric_values["tool_usage_correctness"] = _compute_tool_usage(
                    result_payload.get("tools_used"), expected_tools
                )
            rows.append(
                AgentEvaluationRow(
                    inputs=inputs,
                    answer=answer_val,
                    expected_answer=expected_answer,
                    success=success,
                    latency_seconds=latency,
                    error=error,
                    metrics=metric_values,
                    tools_used=result_payload.get("tools_used"),
                )
            )

        total = len(rows) if rows else 1
        metrics: dict[str, float] = {}
        if "answer_correctness" in metric_names:
            metrics["answer_correctness"] = sum(r.metrics.get("answer_correctness", 0.0) or 0.0 for r in rows) / total
        if "error_rate" in metric_names:
            metrics["error_rate"] = error_count / total
        if "latency_seconds" in metric_names:
            metrics["latency_seconds"] = latency_sum / total
        if "tool_usage_correctness" in metric_names:
            scored = [m for r in rows if (m := r.metrics.get("tool_usage_correctness")) is not None]
            metrics["tool_usage_correctness"] = (sum(scored) / len(scored)) if scored else 0.0

        return AgentEvaluationResult(
            name=eval_cfg.name,
            agent=eval_cfg.agent,
            dataset_frame=eval_cfg.dataset_frame,
            metrics=metrics,
            rows=rows,
            num_rows=len(rows),
        )

    return asyncio.run(_run())


def run_agent_evaluation_by_name(program, flow_engine, evaluation_name: str, limit: Optional[int] = None) -> AgentEvaluationResult:
    eval_cfg = getattr(program, "agent_evaluations", {}).get(evaluation_name)
    if not eval_cfg:
        raise Namel3ssError(f"Agent evaluation '{evaluation_name}' is not declared.")
    return run_agent_evaluation(program, eval_cfg, flow_engine, limit=limit)
