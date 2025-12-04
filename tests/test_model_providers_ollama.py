from namel3ss.ai.providers.ollama import OllamaProvider


def test_ollama_provider_builds_body_and_parses_response():
    captured = {}

    def fake_client(url, body, headers):
        captured["url"] = url
        captured["body"] = body
        return {"message": {"content": "ok"}}

    provider = OllamaProvider(name="ollama", base_url="http://localhost:11434", default_model="llama", http_client=fake_client)
    resp = provider.generate(messages=[{"role": "user", "content": "ping"}])
    assert resp.text == "ok"
    assert captured["url"].endswith("/api/chat")
    assert captured["body"]["model"] == "llama"
