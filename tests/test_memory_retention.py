from datetime import UTC, datetime, timedelta

from namel3ss.memory.models import MemoryNamespace, EpisodicMemoryRecord, RetentionPolicy
from namel3ss.memory.store import MemoryBackend, prune_episodic_memory


def make_record(idx: int, days_ago: int, namespace: MemoryNamespace) -> EpisodicMemoryRecord:
    ts = datetime.now(UTC) - timedelta(days=days_ago)
    return EpisodicMemoryRecord(
        id=f"e{idx}",
        namespace=namespace,
        timestamp=ts,
        kind="event",
        content=f"event {idx}",
        metadata={},
    )


def test_prune_respects_max_episodes_and_age():
    backend = MemoryBackend()
    ns = MemoryNamespace(tenant_id="t", user_id="u", agent_id="a")
    for i in range(6):
        backend.add_episodic(make_record(i, days_ago=i, namespace=ns))
    policy = RetentionPolicy(max_episodes_per_namespace=3, max_age_days=2)
    report = prune_episodic_memory(backend, policy)
    assert report.deleted > 0
    remaining = backend.list_episodic(ns)
    assert len(remaining) <= 3
    assert all((datetime.now(UTC) - r.timestamp).days <= 2 for r in remaining)
