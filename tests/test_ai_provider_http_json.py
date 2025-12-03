import pytest

from namel3ss.ai.http_json_provider import HTTPJsonProvider
from namel3ss.errors import Namel3ssError


def test_http_json_provider_invokes_and_extracts():
    calls = []

    def fake_client(url, body, headers):
        calls.append((url, body, headers))
        assert "messages" in body
        return {"data": {"message": {"content": "ok"}}}

    provider = HTTPJsonProvider(
        name="http_json",
        base_url="http://localhost/api",
        response_path="data.message.content",
        default_model="local-model",
        http_client=fake_client,
    )
    res = provider.invoke(messages=[{"role": "user", "content": "hi"}], temperature=0.1)
    assert res["result"] == "ok"
    assert res["provider"] == "http_json"
    assert calls


def test_http_json_provider_missing_path_raises():
    provider = HTTPJsonProvider(
        name="http_json",
        base_url="http://localhost/api",
        response_path="missing.path",
        default_model="local-model",
        http_client=lambda u, b, h: {"data": {}},
    )
    with pytest.raises(Namel3ssError):
        provider.invoke(messages=[{"role": "user", "content": "hi"}])
