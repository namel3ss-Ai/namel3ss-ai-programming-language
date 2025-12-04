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


default_metrics = MetricsRegistry()
