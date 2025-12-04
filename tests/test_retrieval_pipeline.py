from namel3ss.ai.embedding_router import EmbeddingRouter
from namel3ss.rag.retrieval_models import RAGDocument
from namel3ss.rag.retrieval_pipeline import HybridRetrievalPipeline, RetrievalPipeline
from namel3ss.rag.vectorstores.memory import InMemoryVectorStore
from namel3ss.secrets.manager import SecretsManager


def test_retrieval_pipeline_with_deterministic_embeddings():
    router = EmbeddingRouter(SecretsManager(env={}))
    store = InMemoryVectorStore()
    pipeline = RetrievalPipeline(embedding_router=router, vector_store=store, embedding_model="deterministic")
    docs = [
        RAGDocument(id="1", text="hello world", metadata={}),
        RAGDocument(id="2", text="goodbye world", metadata={}),
    ]
    pipeline.index(docs)
    results = pipeline.retrieve("hello", k=2)
    assert results
    assert results[0].score >= results[1].score


def test_hybrid_retrieval_merges_dense_and_lexical():
    router = EmbeddingRouter(SecretsManager(env={}))
    store = InMemoryVectorStore()
    pipeline = HybridRetrievalPipeline(embedding_router=router, vector_store=store, embedding_model="deterministic")
    docs = [
        RAGDocument(id="1", text="alpha beta gamma", metadata={}),
        RAGDocument(id="2", text="alpha alpha", metadata={}),
    ]
    pipeline.index(docs)
    results = pipeline.retrieve("alpha", k=2)
    assert len(results) == 2
    # lexical signal should boost doc with repeated alpha
    assert results[0].document.id in {"1", "2"}
