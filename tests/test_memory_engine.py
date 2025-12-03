from namel3ss.memory.engine import MemoryEngine
from namel3ss.memory.models import MemorySpaceConfig, MemoryType


def test_memory_engine_records_and_queries():
    engine = MemoryEngine(
        [MemorySpaceConfig(name="short_term", type=MemoryType.CONVERSATION)]
    )
    engine.record_conversation("short_term", "Hello", role="user")
    engine.record_conversation("short_term", "How can I help?", role="assistant")
    recent = engine.get_recent("short_term", limit=2)
    assert len(recent) == 2
    hits = engine.query("short_term", "help")
    assert len(hits) == 1
