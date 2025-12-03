from namel3ss.rag.embeddings_openai import OpenAIEmbeddingProvider


def test_openai_embedding_provider_uses_http_client():
    calls = []

    def fake_client(url, body, headers):
        calls.append((url, body, headers))
        assert body["input"] == ["hello"]
        return {"data": [{"embedding": [0.1, 0.2]}]}

    provider = OpenAIEmbeddingProvider(
        api_key="sk-test",
        base_url="http://api",
        model="text-embedding-3-small",
        http_client=fake_client,
    )
    vec = provider.embed_text("hello")
    assert vec == [0.1, 0.2]
    assert calls
