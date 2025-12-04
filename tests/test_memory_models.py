from datetime import datetime

from namel3ss.memory.models import (
    MemoryNamespace,
    EpisodicMemoryRecord,
    SemanticMemoryRecord,
)


def test_memory_models_hold_namespace_and_content():
    ns = MemoryNamespace(tenant_id="t1", user_id="u1", agent_id="a1")
    ts = datetime(2024, 1, 1)
    episodic = EpisodicMemoryRecord(
        id="e1",
        namespace=ns,
        timestamp=ts,
        kind="event",
        content="detail",
        metadata={"x": 1},
    )
    semantic = SemanticMemoryRecord(
        id="s1",
        namespace=ns,
        created_at=ts,
        source_range={"ids": ["e1"]},
        summary="summary",
        metadata={"y": 2},
    )
    assert episodic.namespace.key() == ("t1", "u1", "a1")
    assert semantic.namespace.key() == ("t1", "u1", "a1")
    assert episodic.content == "detail"
    assert semantic.summary == "summary"
