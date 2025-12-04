from namel3ss.ai.openai_provider import OpenAIProvider


def test_openai_provider_invokes_with_messages_and_params():
    calls = []

    def fake_client(url, body, headers):
        calls.append((url, body, headers))
        assert body["messages"][0]["content"] == "hi"
        assert body["model"] == "gpt-4.1-mini"
        assert body["temperature"] == 0.2
        return {"choices": [{"message": {"content": "response"}}]}

    provider = OpenAIProvider(
        name="openai",
        api_key="sk-test",
        base_url="http://api",
        default_model="gpt-4.1-mini",
        http_client=fake_client,
    )
    res = provider.invoke(messages=[{"role": "user", "content": "hi"}], temperature=0.2)
    assert res.text == "response"
    assert res.provider == "openai"
    assert calls


def test_openai_streaming_yields_delta():
    def fake_stream(url, body, headers):
        yield {"choices": [{"delta": {"content": "chunk1"}}]}
        yield {"choices": [{"delta": {"content": "chunk2"}}]}

    provider = OpenAIProvider(
        name="openai",
        api_key="sk-test",
        base_url="http://api",
        default_model="gpt-4.1-mini",
        http_stream=fake_stream,
    )
    chunks = list(provider.invoke_stream(messages=[{"role": "user", "content": "hi"}]))
    assert chunks[0].delta == "chunk1"
    assert chunks[1].delta == "chunk2"
