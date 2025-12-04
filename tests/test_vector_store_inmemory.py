from namel3ss.rag.retrieval_models import RAGDocument
from namel3ss.rag.vectorstores.memory import InMemoryVectorStore


def test_inmemory_vector_store_index_and_search():
    store = InMemoryVectorStore()
    docs = [
        RAGDocument(id="1", text="hello world", metadata={}),
        RAGDocument(id="2", text="goodbye world", metadata={}),
    ]
    embeddings = [[1.0, 0.0], [0.0, 1.0]]
    store.index(docs, embeddings=embeddings)
    results = store.search_results([1.0, 0.0], k=2)
    assert results[0].document.id == "1"
    assert results[0].rank == 1
    assert results[0].score > results[1].score
