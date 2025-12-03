"""
Metrics tracker for cost and usage.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from .models import CostEvent


class MetricsTracker:
    def __init__(self) -> None:
        self._events: List[CostEvent] = []
        self._flow_counters: Dict[str, int] = defaultdict(int)

    def record_ai_call(
        self, provider: str, tokens_in: int = 0, tokens_out: int = 0, cost: float = 0.0
    ) -> None:
        self._events.append(
            CostEvent(
                operation="ai_call",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=cost,
                provider=provider,
            )
        )

    def record_tool_call(self, provider: str = "tool", cost: float = 0.0) -> None:
        self._events.append(
            CostEvent(
                operation="tool_call",
                tokens_in=0,
                tokens_out=0,
                cost=cost,
                provider=provider,
            )
        )

    def record_agent_run(self, provider: str = "agent", cost: float = 0.0) -> None:
        self._events.append(
            CostEvent(
                operation="agent_run",
                tokens_in=0,
                tokens_out=0,
                cost=cost,
                provider=provider,
            )
        )

    def record_evaluation(self, provider: str = "evaluator", cost: float = 0.0) -> None:
        self._events.append(
            CostEvent(
                operation="agent_evaluation",
                tokens_in=0,
                tokens_out=0,
                cost=cost,
                provider=provider,
            )
        )

    def record_retry(self, provider: str = "retry", cost: float = 0.0) -> None:
        self._events.append(
            CostEvent(
                operation="agent_retry",
                tokens_in=0,
                tokens_out=0,
                cost=cost,
                provider=provider,
            )
        )

    def record_rag_query(self, backends, hybrid_used: bool = False) -> None:
        backend_label = ",".join(backends) if isinstance(backends, list) else str(backends)
        self._events.append(
            CostEvent(
                operation="rag_query_hybrid" if hybrid_used else "rag_query",
                tokens_in=0,
                tokens_out=0,
                cost=0.0,
                provider=backend_label,
            )
        )

    def record_flow_run(self, flow_name: str) -> None:
        self._flow_counters["flows_run"] += 1
        self._flow_counters[f"flow:{flow_name}:runs"] += 1

    def record_flow_error(self, flow_name: str) -> None:
        self._flow_counters["flow_errors"] += 1
        self._flow_counters[f"flow:{flow_name}:errors"] += 1

    def record_parallel_branch(self, count: int) -> None:
        self._flow_counters["parallel_branches"] += count

    def record_trigger_fire(self, kind: str) -> None:
        self._flow_counters["trigger_total"] += 1
        self._flow_counters[f"trigger:{kind}"] += 1

    def snapshot(self) -> Dict[str, Any]:
        by_operation: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "cost": 0.0, "tokens_in": 0, "tokens_out": 0}
        )
        for event in self._events:
            bucket = by_operation[event.operation]
            bucket["count"] += 1
            bucket["cost"] += event.cost
            bucket["tokens_in"] += event.tokens_in
            bucket["tokens_out"] += event.tokens_out
        total_cost = sum(event.cost for event in self._events)
        return {
            "total_cost": total_cost,
            "by_operation": dict(by_operation),
            "flow_metrics": dict(self._flow_counters),
        }
