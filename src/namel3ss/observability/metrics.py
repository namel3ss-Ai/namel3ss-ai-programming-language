"""
Aggregated metrics registry for flows and steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class StepMetricsSnapshot:
    count: int
    total_duration_seconds: float
    total_cost: float


@dataclass
class FlowMetricsSnapshot:
    flow_name: str
    total_runs: int
    avg_duration_seconds: float
    avg_cost: float


class MetricsRegistry:
    def __init__(self) -> None:
        self._step: Dict[str, StepMetricsSnapshot] = {}
        self._flow_counts: Dict[str, FlowMetricsSnapshot] = {}
        self._provider_counts: Dict[tuple[str, str, str], int] = {}
        self._provider_latency: Dict[tuple[str, str], tuple[float, int]] = {}
        self._circuit_open: Dict[str, int] = {}
        self._cache_hits: Dict[tuple[str, str], int] = {}
        self._cache_misses: Dict[tuple[str, str], int] = {}
        self._summary_counts: Dict[str, int] = {}
        self._vector_upserts: int = 0
        self._vector_queries: int = 0

    def record_step(self, step_id: str, duration_seconds: float, cost: float) -> None:
        if step_id not in self._step:
            self._step[step_id] = StepMetricsSnapshot(count=0, total_duration_seconds=0.0, total_cost=0.0)
        snap = self._step[step_id]
        snap.count += 1
        snap.total_duration_seconds += duration_seconds
        snap.total_cost += cost

    def record_flow(self, flow_name: str, duration_seconds: float, cost: float) -> None:
        if flow_name not in self._flow_counts:
            self._flow_counts[flow_name] = FlowMetricsSnapshot(
                flow_name=flow_name, total_runs=0, avg_duration_seconds=0.0, avg_cost=0.0
            )
        snap = self._flow_counts[flow_name]
        snap.total_runs += 1
        snap.avg_duration_seconds = ((snap.avg_duration_seconds * (snap.total_runs - 1)) + duration_seconds) / snap.total_runs
        snap.avg_cost = ((snap.avg_cost * (snap.total_runs - 1)) + cost) / snap.total_runs

    def get_flow_metrics(self) -> Dict[str, FlowMetricsSnapshot]:
        return dict(self._flow_counts)

    def get_step_metrics(self) -> Dict[str, StepMetricsSnapshot]:
        return dict(self._step)

    def record_provider_call(self, provider: str, model: str, status: str, duration_seconds: float) -> None:
        key = (provider or "unknown", model or "unknown", status or "unknown")
        self._provider_counts[key] = self._provider_counts.get(key, 0) + 1
        lat_key = (provider or "unknown", model or "unknown")
        total, count = self._provider_latency.get(lat_key, (0.0, 0))
        self._provider_latency[lat_key] = (total + max(duration_seconds, 0.0), count + 1)

    def record_circuit_open(self, provider: str) -> None:
        key = provider or "unknown"
        self._circuit_open[key] = self._circuit_open.get(key, 0) + 1

    def get_provider_call_counts(self) -> Dict[tuple[str, str, str], int]:
        return dict(self._provider_counts)

    def get_provider_latency(self) -> Dict[tuple[str, str], float]:
        return {key: (total / count if count else 0.0) for key, (total, count) in self._provider_latency.items()}

    def get_circuit_open_counts(self) -> Dict[str, int]:
        return dict(self._circuit_open)

    def record_provider_cache_hit(self, provider: str, model: str) -> None:
        key = (provider or "unknown", model or "unknown")
        self._cache_hits[key] = self._cache_hits.get(key, 0) + 1

    def record_provider_cache_miss(self, provider: str, model: str) -> None:
        key = (provider or "unknown", model or "unknown")
        self._cache_misses[key] = self._cache_misses.get(key, 0) + 1

    def get_provider_cache_hits(self) -> Dict[tuple[str, str], int]:
        return dict(self._cache_hits)

    def get_provider_cache_misses(self) -> Dict[tuple[str, str], int]:
        return dict(self._cache_misses)

    def record_conversation_summary(self, status: str) -> None:
        key = status or "unknown"
        self._summary_counts[key] = self._summary_counts.get(key, 0) + 1

    def record_vector_upsert(self) -> None:
        self._vector_upserts += 1

    def record_vector_query(self) -> None:
        self._vector_queries += 1

    def get_conversation_summary_counts(self) -> Dict[str, int]:
        return dict(self._summary_counts)

    def get_vector_counters(self) -> Dict[str, int]:
        return {
            "upserts": self._vector_upserts,
            "queries": self._vector_queries,
        }


default_metrics = MetricsRegistry()
