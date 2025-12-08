"""
Studio dashboard models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DashboardSummary:
    total_jobs: int
    running_jobs: int
    failed_jobs: int
    total_flows: int
    total_agents: int
    total_plugins: int
    memory_items: int
    rag_documents: int
    ai_calls: list[str]
