"""
Summarization worker that converts episodic memories into semantic summaries.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional

from .models import EpisodicMemoryRecord, MemoryNamespace, RetentionPolicy, SemanticMemoryRecord
from .store import MemoryBackend, prune_episodic_memory


@dataclass
class SummarizationReport:
    namespaces_processed: int
    summaries_created: int
    pruned: int


class MemorySummarizationWorker:
    def __init__(
        self,
        backend: MemoryBackend,
        model_router,
        retention_policy: Optional[RetentionPolicy] = None,
        min_age_seconds: int = 0,
        max_window: int = 10,
    ) -> None:
        self.backend = backend
        self.model_router = model_router
        self.retention_policy = retention_policy
        self.min_age_seconds = min_age_seconds
        self.max_window = max_window

    async def run_once(self) -> SummarizationReport:
        namespaces = {r.namespace.key() for r in self.backend.episodic}
        summaries_created = 0
        for ns_key in namespaces:
            ns = MemoryNamespace(*ns_key)
            records = [r for r in self.backend.episodic if r.namespace.key() == ns_key]
            records.sort(key=lambda r: r.timestamp)
            eligible = [
                r for r in records if (datetime.now(UTC) - r.timestamp).total_seconds() >= self.min_age_seconds
            ]
            if not eligible:
                continue
            windows = [eligible[i : i + self.max_window] for i in range(0, len(eligible), self.max_window)]
            for window in windows:
                summary = await self._summarize_window(ns, window)
                self.backend.add_semantic(summary)
                summaries_created += 1
        pruned = 0
        if self.retention_policy:
            report = prune_episodic_memory(self.backend, self.retention_policy)
            pruned = report.deleted
        return SummarizationReport(
            namespaces_processed=len(namespaces),
            summaries_created=summaries_created,
            pruned=pruned,
        )

    async def _summarize_window(self, namespace: MemoryNamespace, window: list[EpisodicMemoryRecord]) -> SemanticMemoryRecord:
        prompt = self._build_prompt(namespace, window)
        response = self.model_router.generate(messages=[{"role": "user", "content": prompt}])
        summary_text = getattr(response, "text", None) or str(response)
        return SemanticMemoryRecord(
            id=str(uuid.uuid4()),
            namespace=namespace,
            created_at=datetime.now(UTC),
            source_range={
                "from": window[0].timestamp.isoformat(),
                "to": window[-1].timestamp.isoformat(),
                "ids": [r.id for r in window],
            },
            summary=summary_text,
            metadata={"count": len(window)},
        )

    def _build_prompt(self, namespace: MemoryNamespace, window: list[EpisodicMemoryRecord]) -> str:
        lines = [f"[{r.kind}] {r.content}" for r in window]
        ns_label = f"tenant={namespace.tenant_id or 'default'}, user={namespace.user_id or 'anon'}, agent={namespace.agent_id or 'agent'}"
        return (
            f"Summarize the following episodic events for {ns_label}.\n"
            + "\n".join(lines)
            + "\nProvide a concise summary."
        )
