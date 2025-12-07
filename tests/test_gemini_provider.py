import pytest

from namel3ss.ai.providers.gemini import GeminiProvider
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.errors import Namel3ssError
from namel3ss.secrets.manager import SecretsManager


def test_gemini_provider_happy_path():
    secrets = SecretsManager(env={"GEMINI_API_KEY": "sk-test"})
    registry = ModelRegistry(secrets=secrets)
    registry.register_model("gemini-chat", "gemini:gemini-1.5-pro")
    provider: GeminiProvider = registry.get_provider_for_model("gemini-chat")  # type: ignore[assignment]

    def fake_client(url, body, headers):
        assert "generativelanguage.googleapis.com" in url
        assert body["contents"]
        return {"candidates": [{"content": {"parts": [{"text": "hello"}]}, "finish_reason": "stop"}]}

    provider._http_client = fake_client  # type: ignore[attr-defined]
    router = ModelRouter(registry, secrets=secrets)
    resp = router.generate(messages=[{"role": "user", "content": "hi"}], model="gemini-chat")
    assert resp.text == "hello"
    assert resp.provider == "gemini"


def test_gemini_provider_missing_key_errors(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    secrets = SecretsManager(env={})
    registry = ModelRegistry(secrets=secrets)
    with pytest.raises(Namel3ssError):
        registry.register_model("gemini-chat", "gemini:gemini-1.5-pro")
