from namel3ss.ai.models import ModelStreamChunk
from namel3ss.ai.providers.openai import OpenAIProvider


def test_openai_provider_generate_parses_content_and_usage():
    calls = []

    def fake_client(url, body, headers):
        calls.append((url, body, headers))
        return {
            "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        }

    provider = OpenAIProvider(name="openai", api_key="sk-test", default_model="gpt-4o", http_client=fake_client)
    resp = provider.generate(messages=[{"role": "user", "content": "ping"}])
    assert resp.text == "hello"
    assert resp.finish_reason == "stop"
    assert resp.usage and resp.usage.total_tokens == 5
    assert calls


def test_openai_provider_stream_yields_chunks():
    def fake_stream(url, body, headers):
        yield {"choices": [{"delta": {"content": "a"}}]}
        yield {"choices": [{"delta": {"content": "b"}, "finish_reason": "stop"}]}

    provider = OpenAIProvider(
        name="openai",
        api_key="sk-test",
        default_model="gpt-4o",
        http_stream=fake_stream,
    )
    chunks = list(provider.stream(messages=[{"role": "user", "content": "hi"}]))
    assert len(chunks) == 2
    assert all(isinstance(c, ModelStreamChunk) for c in chunks)
    assert chunks[0].delta == "a"
    assert chunks[1].is_final is True
