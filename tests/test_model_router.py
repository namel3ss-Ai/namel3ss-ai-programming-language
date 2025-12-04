from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ai.providers import DummyProvider
from namel3ss.ai.providers.openai import OpenAIProvider
from namel3ss.secrets.manager import SecretsManager


def test_router_generate_with_registered_openai_model(monkeypatch):
    secrets = SecretsManager(env={"N3_OPENAI_API_KEY": "sk-test"})
    registry = ModelRegistry(secrets=secrets)
    registry.register_model("logical", "openai:gpt-test")
    provider: OpenAIProvider = registry.get_provider_for_model("logical")  # type: ignore[assignment]

    def fake_client(url, body, headers):
        return {"choices": [{"message": {"content": "ok"}}]}

    provider._http_client = fake_client  # type: ignore[attr-defined]
    router = ModelRouter(registry, secrets=secrets)
    resp = router.generate(messages=[{"role": "user", "content": "ping"}], model="logical")
    assert resp.text == "ok"
    assert resp.model == "gpt-test"


def test_router_generate_with_prefix_registers_dummy_without_key():
    secrets = SecretsManager(env={})
    registry = ModelRegistry(secrets=secrets)
    router = ModelRouter(registry, secrets=secrets)
    resp = router.generate(messages=[{"role": "user", "content": "hi"}], model="openai:gpt-4o")
    assert "dummy output" in resp.text


def test_router_stream_uses_provider_stream(monkeypatch):
    secrets = SecretsManager(env={"N3_OPENAI_API_KEY": "sk-test"})
    registry = ModelRegistry(secrets=secrets)
    registry.register_model("logical", "openai:gpt-test")
    provider: OpenAIProvider = registry.get_provider_for_model("logical")  # type: ignore[assignment]

    def fake_stream(url, body, headers):
        yield {"choices": [{"delta": {"content": "a"}}]}

    provider._http_stream = fake_stream  # type: ignore[attr-defined]
    router = ModelRouter(registry, secrets=secrets)
    chunks = list(router.stream(messages=[{"role": "user", "content": "ping"}], model="logical"))
    assert chunks and chunks[0].delta == "a"


def test_auto_select_prefers_gemini_when_available():
    secrets = SecretsManager(env={"N3_GEMINI_API_KEY": "gem-key"})
    registry = ModelRegistry(secrets=secrets)
    router = ModelRouter(registry, secrets=secrets)
    selection = router.auto_select()
    assert selection.provider_name == "gemini"
