import pytest

from namel3ss.rag.vectorstores.faiss import FAISSVectorStore, faiss
from namel3ss.rag.models import RAGItem


@pytest.mark.skipif(faiss is None, reason="faiss not installed")
def test_faiss_vector_store_search():
    store = FAISSVectorStore(dimension=3)
    items = [
        RAGItem(id="1", text="a", embedding=[1.0, 0.0, 0.0], source="faiss"),
        RAGItem(id="2", text="b", embedding=[0.0, 1.0, 0.0], source="faiss"),
    ]
    store.add_sync(items)
    res = store.search([1.0, 0.0, 0.0], top_k=1)
    assert res
    assert res[0].item.id == "1"
