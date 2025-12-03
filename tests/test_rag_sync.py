import asyncio

from namel3ss.memory.engine import ShardedMemoryEngine
from namel3ss.memory.models import MemorySpaceConfig, MemoryType
from namel3ss.rag.engine import RAGEngine
from namel3ss.rag.sync import RAGSyncWorker


def test_rag_sync_worker_ingests_memory():
    memory = ShardedMemoryEngine([MemorySpaceConfig(name="short", type=MemoryType.CONVERSATION)])
    rag = RAGEngine()
    memory.record_conversation("short", "Hello world", role="user")
    worker = RAGSyncWorker(memory, rag)
    asyncio.run(worker.run_once("short"))
    results = rag.store.search([0.0] * 8, top_k=5)
    assert results
