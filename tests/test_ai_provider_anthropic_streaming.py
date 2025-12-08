from namel3ss.ai.providers.anthropic import AnthropicProvider


def test_anthropic_streaming_yields_delta():
    def fake_stream(url, body, headers):
        yield {"delta": {"text": "a1"}}
        yield {"delta": {"text": "a2"}}

    provider = AnthropicProvider(
        name="anthropic",
        api_key="test-key",
        default_model="claude-3-opus",
        http_stream=fake_stream,
    )
    chunks = list(provider.stream(messages=[{"role": "user", "content": "hi"}]))
    assert [c.delta for c in chunks] == ["a1", "a2"]
