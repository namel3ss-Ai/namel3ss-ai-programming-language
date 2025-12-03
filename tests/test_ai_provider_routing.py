from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ai.openai_provider import OpenAIProvider
from namel3ss.ai.providers import DummyProvider
from namel3ss.secrets.manager import SecretsManager


def test_openai_provider_selected_when_key_present():
    secrets = SecretsManager(env={"N3_OPENAI_API_KEY": "sk-test", "N3_OPENAI_BASE_URL": "http://example"})
    registry = ModelRegistry(secrets=secrets)
    registry.register_model("logical", "openai:gpt-test")
    router = ModelRouter(registry)
    selection = router.select_model("logical")
    provider = registry.get_provider_for_model("logical")
    assert selection.provider_name == "openai:gpt-test"
    assert isinstance(provider, OpenAIProvider)

    calls = []

    def fake_client(url, body):
        calls.append((url, body))
        return {"choices": [{"message": {"content": "ok"}}]}

    provider._http_client = fake_client  # type: ignore[attr-defined]
    result = provider.invoke("hello", model="gpt-test")
    assert result["result"] == "ok"
    assert calls, "HTTP client should have been invoked"


def test_openai_provider_falls_back_to_dummy_without_key():
    secrets = SecretsManager(env={})
    registry = ModelRegistry(secrets=secrets)
    registry.register_model("logical", "openai:gpt-test")
    provider = registry.get_provider_for_model("logical")
    assert isinstance(provider, DummyProvider)
    out = provider.invoke("ping")
    assert "dummy output" in out["result"]


def test_dummy_provider_default():
    registry = ModelRegistry()
    registry.register_model("logical", None)
    router = ModelRouter(registry)
    selection = router.select_model("logical")
    assert selection.provider_name == "dummy"
    provider = registry.get_provider_for_model("logical")
    assert isinstance(provider, DummyProvider)
