"""
Studio engine building dashboard summaries.
"""

from __future__ import annotations

from typing import Any

from .models import DashboardSummary


class StudioEngine:
    def __init__(
        self,
        job_queue,
        tracer,
        metrics_tracker,
        memory_engine,
        rag_engine,
        ir_program,
        plugin_registry,
    ) -> None:
        self.job_queue = job_queue
        self.tracer = tracer
        self.metrics_tracker = metrics_tracker
        self.memory_engine = memory_engine
        self.rag_engine = rag_engine
        self.ir_program = ir_program
        self.plugin_registry = plugin_registry

    def build_summary(self) -> DashboardSummary:
        jobs = self.job_queue.list() if self.job_queue else []
        total_jobs = len(jobs)
        running_jobs = len([j for j in jobs if j.status == "running"])
        failed_jobs = len([j for j in jobs if j.status == "error"])

        total_flows = len(getattr(self.ir_program, "flows", {}))
        total_agents = len(getattr(self.ir_program, "agents", {}))
        total_plugins = len(getattr(self.plugin_registry, "list_plugins", lambda: [])())

        memory_items = 0
        if self.memory_engine:
            spaces = getattr(self.memory_engine, "spaces", {}) or {}
            for space in spaces:
                memory_items += len(self.memory_engine.store.list(space))

        rag_documents = 0
        if self.rag_engine and hasattr(self.rag_engine, "store"):
            rag_documents = len(getattr(self.rag_engine.store, "_chunks", []))

        ai_calls = list((getattr(self.ir_program, "ai_calls", {}) or {}).keys())

        return DashboardSummary(
            total_jobs=total_jobs,
            running_jobs=running_jobs,
            failed_jobs=failed_jobs,
            total_flows=total_flows,
            total_agents=total_agents,
            total_plugins=total_plugins,
            memory_items=memory_items,
            rag_documents=rag_documents,
            ai_calls=ai_calls,
        )
