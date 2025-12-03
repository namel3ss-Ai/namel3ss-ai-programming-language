from namel3ss.rag.embeddings_deterministic import DeterministicEmbeddingProvider


def test_deterministic_embedding_reproducible():
    provider = DeterministicEmbeddingProvider(dimensions=8)
    v1 = provider.embed_text("hello world")
    v2 = provider.embed_text("hello world")
    assert v1 == v2
    batch = provider.embed_batch(["hello", "world"])
    assert batch[0] == provider.embed_text("hello")
    assert batch[1] == provider.embed_text("world")
