"""
Lightweight RAG evaluation runner.

Executes a declared RAG pipeline against a dataset frame and computes simple,
deterministic metrics per row plus aggregates.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from ..errors import Namel3ssError
from ..flows.graph import FlowState
from ..runtime.context import ExecutionContext
from ..obs.tracer import Tracer


@dataclass
class RagEvaluationRow:
    question: str
    expected_answer: Optional[str]
    answer: Optional[str]
    metrics: Dict[str, Optional[float]]
    error: Optional[str] = None
    context: Optional[str] = None


@dataclass
class RagEvaluationResult:
    name: str
    pipeline: str
    dataset_frame: str
    question_column: str
    answer_column: Optional[str]
    metrics: List[str] = field(default_factory=list)
    rows: List[RagEvaluationRow] = field(default_factory=list)
    aggregates: Dict[str, Dict[str, float | int]] = field(default_factory=dict)
    num_rows: int = 0


def _normalize_words(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(re.findall(r"[A-Za-z0-9]+", str(text).lower()))


def _overlap_score(base: Iterable[str], other: Iterable[str]) -> float:
    base_set = set(base)
    other_set = set(other)
    if not base_set or not other_set:
        return 0.0
    return min(1.0, len(base_set & other_set) / len(base_set))


def _compute_metrics(
    metric_names: list[str],
    question: str | None,
    answer: str | None,
    expected: str | None,
    context: str | None,
) -> Dict[str, Optional[float]]:
    q_words = _normalize_words(question)
    a_words = _normalize_words(answer)
    e_words = _normalize_words(expected)
    c_words = _normalize_words(context)
    scores: Dict[str, Optional[float]] = {}
    for name in metric_names:
        if name == "context_relevance":
            scores[name] = _overlap_score(q_words, c_words)
        elif name == "answer_faithfulness":
            scores[name] = _overlap_score(a_words, c_words)
        elif name == "answer_completeness":
            scores[name] = None if not expected else _overlap_score(e_words, a_words)
        else:
            scores[name] = None
    return scores


def _compute_aggregates(rows: list[RagEvaluationRow], metric_names: list[str]) -> dict[str, dict[str, float | int]]:
    aggregates: dict[str, dict[str, float | int]] = {}
    for name in metric_names:
        values = [m for row in rows if (m := row.metrics.get(name)) is not None]
        count = len(values)
        mean = float(sum(values) / count) if count else 0.0
        aggregates[name] = {"mean": mean, "count": count}
    return aggregates


async def _run_single_question(flow_engine, eval_cfg, question: str, base_context: ExecutionContext, runtime_ctx, flow_name: str):
    state = FlowState(context={"flow_name": flow_name})
    result = await flow_engine._run_rag_pipeline(
        eval_cfg.pipeline,
        question,
        state,
        runtime_ctx,
        base_context,
        flow_name=flow_name,
        step_name="rag_eval",
    )
    return {
        "answer": result.get("answer"),
        "context": result.get("context") or "",
    }


def run_rag_evaluation(program, eval_cfg, flow_engine, limit: Optional[int] = None) -> RagEvaluationResult:
    """
    Execute a RAG evaluation synchronously.

    Args:
        program: IRProgram containing pipelines/frames.
        eval_cfg: IRRagEvaluation configuration.
        flow_engine: FlowEngine instance with registries initialized.
        limit: Optional cap on rows evaluated.
    """

    async def _run() -> RagEvaluationResult:
        frame_registry = getattr(flow_engine, "frame_registry", None)
        if not frame_registry:
            raise Namel3ssError("Frame registry is not available for RAG evaluation.")
        rows_data = frame_registry.get_rows(eval_cfg.dataset_frame)
        if limit is not None:
            try:
                lim = int(limit)
            except Exception:
                lim = None
            if lim is not None and lim >= 0:
                rows_data = rows_data[:lim]

        base_context = ExecutionContext(
            app_name="rag_evaluation",
            request_id=str(uuid4()),
            tracer=Tracer(),
            metrics=getattr(flow_engine, "metrics", None),
            secrets=getattr(flow_engine, "secrets", None),
        )
        runtime_ctx = flow_engine._build_runtime_context(base_context)

        rows: list[RagEvaluationRow] = []
        metric_names = list(eval_cfg.metrics or [])
        flow_name = f"rag_eval:{eval_cfg.name}"

        for row in rows_data:
            error: Optional[str] = None
            question_val: Optional[str] = None
            expected_val: Optional[str] = None
            answer_val: Optional[str] = None
            context_text: Optional[str] = None
            try:
                if isinstance(row, dict):
                    question_val = row.get(eval_cfg.question_column)
                    if eval_cfg.answer_column:
                        expected_val = row.get(eval_cfg.answer_column)
                else:
                    raise Namel3ssError("Frame rows must be records for RAG evaluation.")
                if question_val is None:
                    raise Namel3ssError(
                        f"Row is missing question_column '{eval_cfg.question_column}'."
                    )
                question_text = str(question_val)
                single_result = await _run_single_question(
                    flow_engine, eval_cfg, question_text, base_context, runtime_ctx, flow_name
                )
                answer_val = single_result.get("answer")
                context_text = single_result.get("context")
            except Exception as exc:
                error = str(exc)
                answer_val = None
                context_text = context_text or ""
            metrics = _compute_metrics(metric_names, question_val, answer_val, expected_val, context_text)
            rows.append(
                RagEvaluationRow(
                    question=str(question_val) if question_val is not None else "",
                    expected_answer=str(expected_val) if expected_val is not None else None,
                    answer=answer_val if answer_val is None or isinstance(answer_val, str) else str(answer_val),
                    metrics=metrics,
                    error=error,
                    context=context_text,
                )
            )

        aggregates = _compute_aggregates(rows, metric_names)
        return RagEvaluationResult(
            name=eval_cfg.name,
            pipeline=eval_cfg.pipeline,
            dataset_frame=eval_cfg.dataset_frame,
            question_column=eval_cfg.question_column,
            answer_column=eval_cfg.answer_column,
            metrics=metric_names,
            rows=rows,
            aggregates=aggregates,
            num_rows=len(rows),
        )

    return asyncio.run(_run())


def run_rag_evaluation_by_name(program, flow_engine, evaluation_name: str, limit: Optional[int] = None) -> RagEvaluationResult:
    eval_cfg = getattr(program, "rag_evaluations", {}).get(evaluation_name)
    if not eval_cfg:
        raise Namel3ssError(f"RAG evaluation '{evaluation_name}' is not declared.")
    return run_rag_evaluation(program, eval_cfg, flow_engine, limit=limit)
