import pytest

from namel3ss.rag.embeddings_http_json import HTTPJsonEmbeddingProvider
from namel3ss.errors import Namel3ssError


def test_http_json_embeddings_extracts_response():
    def fake_client(url, body, headers):
        assert "texts" in body
        return {"data": {"embedding": [[0.5, 0.6]]}}

    provider = HTTPJsonEmbeddingProvider(
        base_url="http://localhost/emb",
        response_path="data.embedding",
        model="local",
        http_client=fake_client,
    )
    vecs = provider.embed_batch(["hi"])
    assert vecs == [[0.5, 0.6]]


def test_http_json_embeddings_missing_path_raises():
    provider = HTTPJsonEmbeddingProvider(
        base_url="http://localhost/emb",
        response_path="missing.path",
        model="local",
        http_client=lambda u, b, h: {"data": {}},
    )
    with pytest.raises(Namel3ssError):
        provider.embed_text("hi")
