import asyncio

from namel3ss.rag.engine import RAGEngine
from namel3ss.rag.index_config import RAGIndexConfig
from namel3ss.rag.models import RAGItem, ScoredItem
from namel3ss.rag.store import embed_text
from namel3ss.memory.engine import MemoryEngine
from namel3ss.memory.models import MemorySpaceConfig, MemoryType


def test_multi_index_and_hybrid():
    engine = RAGEngine(indexes=[RAGIndexConfig(name="a", enable_hybrid=True), RAGIndexConfig(name="b")])
    asyncio.run(engine.a_index_documents("a", ["hello world", "foo bar"]))
    asyncio.run(engine.a_index_documents("b", ["another doc", "hello planet"]))

    res = asyncio.run(engine.a_retrieve("hello", index_names=["a", "b"]))
    assert res
    sources = {r.source for r in res}
    assert "a" in sources and "b" in sources


def test_cross_store_includes_memory():
    mem_engine = MemoryEngine([MemorySpaceConfig(name="short", type=MemoryType.CONVERSATION)])
    mem_engine.record_conversation("short", "memory hello text", role="user")
    engine = RAGEngine(indexes=[RAGIndexConfig(name="a")], memory_engine=mem_engine)
    asyncio.run(engine.a_index_documents("a", ["irrelevant"]))
    res = asyncio.run(engine.a_retrieve("memory hello"))
    assert any(r.source.startswith("memory") for r in res)


def test_rerank_and_rewrite_deterministic():
    engine = RAGEngine(indexes=[RAGIndexConfig(name="a", enable_rerank=True, enable_rewrite=True)])
    asyncio.run(engine.a_index_documents("a", ["Alpha content", "beta data"]))
    res = asyncio.run(engine.a_retrieve("Alpha"))
    assert res
    # alpha should be top after rerank
    assert res[0].item.text.lower().startswith("alpha")
