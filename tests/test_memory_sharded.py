from namel3ss.memory.engine import ShardedMemoryEngine
from namel3ss.memory.models import MemorySpaceConfig, MemoryType


def test_sharded_memory_distribution_and_query():
    spaces = [MemorySpaceConfig(name="short", type=MemoryType.CONVERSATION)]
    engine = ShardedMemoryEngine(spaces, num_shards=3)
    # add items
    for idx in range(6):
        engine.record_conversation("short", f"msg-{idx}", role="user")
    # ensure multiple shards are used
    shard_counts = [len(store.list("short")) for store in engine._stores]
    assert sum(1 for c in shard_counts if c > 0) >= 2
    all_items = engine.list_all("short")
    assert len(all_items) == 6
    hits = engine.query("short", "msg-1")
    assert hits
