from namel3ss.rag.engine import RAGEngine
from namel3ss.rag.store import embed_text


def test_embed_text_is_deterministic():
    v1 = embed_text("hello")
    v2 = embed_text("hello")
    assert v1 == v2
    assert len(v1) == len(v2)


def test_rag_engine_retrieve():
    rag = RAGEngine()
    rag.index_documents("help_docs", ["reset password", "update billing info"])
    results = rag.retrieve(source="help_docs", query="password", top_k=1)
    assert results
    assert results[0].source == "help_docs"
