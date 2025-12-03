from namel3ss.memory.engine import MemoryEngine, PersistentMemoryEngine
from namel3ss.memory.models import MemorySpaceConfig, MemoryType


def test_persistent_memory_round_trip(tmp_path):
    db_path = tmp_path / "memory.db"
    spaces = [MemorySpaceConfig(name="short", type=MemoryType.CONVERSATION)]
    engine1 = PersistentMemoryEngine(spaces, db_path=str(db_path))
    engine1.record_conversation("short", "hello world", role="user")

    engine2 = PersistentMemoryEngine(spaces, db_path=str(db_path))
    items = engine2.get_recent("short", limit=5)
    assert any(item.content == "hello world" for item in items)


def test_in_memory_not_persistent(tmp_path):
    spaces = [MemorySpaceConfig(name="short", type=MemoryType.CONVERSATION)]
    engine1 = MemoryEngine(spaces)
    engine1.record_conversation("short", "ephemeral", role="user")
    engine2 = MemoryEngine(spaces)
    items = engine2.get_recent("short", limit=5)
    assert not any(item.content == "ephemeral" for item in items)
