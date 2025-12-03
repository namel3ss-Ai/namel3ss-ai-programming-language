import asyncio

from namel3ss.rag.models import RAGItem
from namel3ss.rag.vectorstores.memory import InMemoryVectorStore
from namel3ss.rag.store import embed_text


def test_in_memory_vector_store_add_query_delete():
    store = InMemoryVectorStore()
    items = [
        RAGItem(id="1", text="hello world", embedding=embed_text("hello"), source="idx"),
        RAGItem(id="2", text="another text", embedding=embed_text("another"), source="idx"),
    ]
    asyncio.run(store.a_add(items))
    res = asyncio.run(store.a_query(embed_text("hello"), k=2))
    assert res
    assert res[0].item.id == "1"
    asyncio.run(store.a_delete(["1"]))
    res2 = asyncio.run(store.a_query(embed_text("hello"), k=2))
    assert all(r.item.id != "1" for r in res2)
