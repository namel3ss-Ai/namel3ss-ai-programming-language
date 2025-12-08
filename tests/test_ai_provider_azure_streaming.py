from namel3ss.ai.providers.azure_openai import AzureOpenAIProvider


def test_azure_openai_streaming_yields_delta():
    def fake_stream(url, body, headers):
        yield {"choices": [{"delta": {"content": "az1"}}]}
        yield {"choices": [{"delta": {"content": "az2"}}]}

    provider = AzureOpenAIProvider(
        name="azure_openai",
        api_key="sk-test",
        base_url="http://azure",
        deployment="gpt4o",
        api_version="2024-06-01",
        http_stream=fake_stream,
    )
    chunks = list(provider.stream(messages=[{"role": "user", "content": "hi"}]))
    assert [c.delta for c in chunks] == ["az1", "az2"]
