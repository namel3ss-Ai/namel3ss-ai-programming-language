"""
Memory 2.0 in-memory backend and retention helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .models import EpisodicMemoryRecord, MemoryNamespace, RetentionPolicy, SemanticMemoryRecord
from .backends.in_memory import InMemoryMemoryStore  # backward compatibility re-export


class MemoryBackend:
    """
    Lightweight in-memory backend for episodic and semantic records with namespaces.
    """

    def __init__(self) -> None:
        self.episodic: List[EpisodicMemoryRecord] = []
        self.semantic: List[SemanticMemoryRecord] = []

    def add_episodic(self, record: EpisodicMemoryRecord) -> EpisodicMemoryRecord:
        self.episodic.append(record)
        return record

    def add_semantic(self, record: SemanticMemoryRecord) -> SemanticMemoryRecord:
        self.semantic.append(record)
        return record

    def list_episodic(self, namespace: Optional[MemoryNamespace] = None) -> List[EpisodicMemoryRecord]:
        if namespace is None:
            return list(self.episodic)
        return [r for r in self.episodic if r.namespace.key() == namespace.key()]

    def list_semantic(self, namespace: Optional[MemoryNamespace] = None) -> List[SemanticMemoryRecord]:
        if namespace is None:
            return list(self.semantic)
        return [r for r in self.semantic if r.namespace.key() == namespace.key()]

    def delete_episodic(self, ids: List[str]) -> None:
        ids_set = set(ids)
        self.episodic = [r for r in self.episodic if r.id not in ids_set]


@dataclass
class PruneReport:
    deleted: int
    per_namespace: Dict[Tuple[str, str, str], int]


def prune_episodic_memory(backend: MemoryBackend, policy: RetentionPolicy) -> PruneReport:
    per_namespace: Dict[Tuple[str, str, str], int] = {}
    now = datetime.now(UTC)
    to_delete: List[str] = []
    for namespace_key in {r.namespace.key() for r in backend.episodic}:
        records = [r for r in backend.episodic if r.namespace.key() == namespace_key]
        records.sort(key=lambda r: r.timestamp, reverse=True)
        remove_ids: List[str] = []
        if policy.max_episodes_per_namespace is not None and len(records) > policy.max_episodes_per_namespace:
            remove_ids.extend([r.id for r in records[policy.max_episodes_per_namespace :]])
        if policy.max_age_days is not None:
            cutoff = now - timedelta(days=policy.max_age_days)
            remove_ids.extend([r.id for r in records if r.timestamp < cutoff])
        if remove_ids:
            per_namespace[namespace_key] = len(remove_ids)
            to_delete.extend(remove_ids)
    backend.delete_episodic(to_delete)
    return PruneReport(deleted=len(to_delete), per_namespace=per_namespace)
