import pytest

from namel3ss.ai.http_json_provider import HTTPJsonProvider
from namel3ss.errors import Namel3ssError


def test_http_json_provider_invokes_and_extracts_default_content():
    calls = []

    def fake_client(url, body, headers):
        calls.append((url, body, headers))
        assert url == "http://localhost:11434/api/chat"
        assert body["model"] == "local-llama"
        assert "messages" in body
        return {"content": "ok"}

    provider = HTTPJsonProvider(
        name="http_json",
        base_url="http://localhost:11434",
        path="/api/chat",
        default_model="local-llama",
        http_client=fake_client,
    )
    res = provider.invoke(messages=[{"role": "user", "content": "hi"}], temperature=0.1)
    assert res["result"] == "ok"
    assert res["provider"] == "http_json"
    assert calls


def test_http_json_provider_nested_response_path():
    provider = HTTPJsonProvider(
        name="http_json",
        base_url="http://localhost/api",
        path="/chat",
        response_path="data.message.content",
        default_model="local-model",
        http_client=lambda u, b, h: {"data": {"message": {"content": "nested-ok"}}},
    )
    res = provider.invoke(messages=[{"role": "user", "content": "hi"}])
    assert res["result"] == "nested-ok"


def test_http_json_provider_missing_content_raises():
    provider = HTTPJsonProvider(
        name="http_json",
        base_url="http://localhost/api",
        path="/chat",
        default_model="local-model",
        http_client=lambda u, b, h: {"data": {}},
    )
    with pytest.raises(Namel3ssError):
        provider.invoke(messages=[{"role": "user", "content": "hi"}])


def test_http_json_provider_streams_single_chunk():
    provider = HTTPJsonProvider(
        name="http_json",
        base_url="http://localhost/api",
        path="/chat",
        default_model="local-model",
        http_client=lambda u, b, h: {"content": "streamed"},
    )
    chunks = list(provider.invoke_stream(messages=[{"role": "user", "content": "hello"}]))
    assert len(chunks) == 1
    assert chunks[0].delta == "streamed"
