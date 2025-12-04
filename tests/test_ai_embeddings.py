from namel3ss.ai.embedding_router import EmbeddingRouter
from namel3ss.ai.embeddings import DeterministicEmbeddingProvider
from namel3ss.ai.embeddings.http_generic import HTTPEmbeddingProvider
from namel3ss.ai.embeddings.openai import OpenAIEmbeddingProvider
from namel3ss.secrets.manager import SecretsManager


def test_deterministic_embeddings_are_stable():
    provider = DeterministicEmbeddingProvider(dimensions=4)
    vec1 = provider.embed(["hello"]).vectors[0]
    vec2 = provider.embed(["hello"]).vectors[0]
    assert vec1 == vec2
    assert len(vec1) == 4


def test_openai_embeddings_maps_response():
    def fake_client(url, body, headers):
        assert body["input"] == ["a", "b"]
        return {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}

    provider = OpenAIEmbeddingProvider(api_key="sk-test", model="text-embed", http_client=fake_client)
    result = provider.embed(["a", "b"])
    assert result.vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert result.dim == 2


def test_http_embedding_provider_uses_response_path():
    provider = HTTPEmbeddingProvider(
        base_url="http://example",
        response_path="data.vecs",
        http_client=lambda url, body, headers: {"data": {"vecs": [[0.5, 0.6]]}},
    )
    result = provider.embed(["x"])
    assert result.vectors[0] == [0.5, 0.6]


def test_embedding_router_routes_by_prefix():
    secrets = SecretsManager(env={"N3_OPENAI_API_KEY": "sk-test", "N3_OPENAI_BASE_URL": "http://api"})
    router = EmbeddingRouter(secrets)

    def fake_client(url, body, headers):
        return {"data": [{"embedding": [1.0, 2.0]}]}

    # Patch provider creation to use fake client
    provider = OpenAIEmbeddingProvider(api_key="sk-test", http_client=fake_client)
    router._cache["openai"] = provider
    result = router.embed(["hello"], model="openai:text-embedding-3-small")
    assert result.vectors == [[1.0, 2.0]]


def test_embedding_router_auto_uses_deterministic_when_no_keys():
    router = EmbeddingRouter(SecretsManager(env={}))
    result = router.embed(["hi"], model="auto")
    assert result.vectors and len(result.vectors[0]) > 0
