import os

import pytest

from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ai.config import default_global_ai_config
from namel3ss.ai.providers.anthropic import AnthropicProvider
from namel3ss.config import load_config
from namel3ss.errors import Namel3ssError, ProviderConfigError
from namel3ss.secrets.manager import SecretsManager


def test_load_config_env(monkeypatch):
    monkeypatch.setenv("N3_DEFAULT_CHAT_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("N3_DEFAULT_EMBEDDING_MODEL", "text-embedding-3-large")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp.db")
    cfg = load_config()
    assert cfg.default_chat_model == "openai:gpt-4.1-mini"
    assert cfg.default_embedding_model == "text-embedding-3-large"
    assert cfg.database_url == "sqlite:///tmp.db"
    assert cfg.providers_config is not None


def test_model_router_uses_default_chat_model(monkeypatch):
    monkeypatch.setenv("N3_DEFAULT_CHAT_MODEL", "dummy")
    secrets = SecretsManager(env={})
    registry = ModelRegistry(secrets=secrets)
    router = ModelRouter(registry, config=default_global_ai_config(), secrets=secrets)
    resp = router.generate(messages=[{"role": "user", "content": "hi"}])
    assert "dummy output" in resp.text


def test_missing_openai_key_errors(monkeypatch):
    monkeypatch.delenv("N3_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    secrets = SecretsManager(env={})
    registry = ModelRegistry(secrets=secrets)
    router = ModelRouter(registry, secrets=secrets)
    with pytest.raises(ProviderConfigError):
        router._provider_for_prefix("openai", default_model=None)  # type: ignore[attr-defined]


def test_anthropic_provider_with_key():
    secrets = SecretsManager(env={"ANTHROPIC_API_KEY": "sk-test"})
    registry = ModelRegistry(secrets=secrets)
    registry.register_model("claude", "anthropic:claude-3-opus")
    provider: AnthropicProvider = registry.get_provider_for_model("claude")  # type: ignore[assignment]

    def fake_client(url, body, headers):
        return {"content": [{"text": "ok"}], "usage": {"input_tokens": 1, "output_tokens": 1}}

    provider._http_client = fake_client  # type: ignore[attr-defined]
    router = ModelRouter(registry, secrets=secrets)
    resp = router.generate(messages=[{"role": "user", "content": "ping"}], model="claude")
    assert resp.text == "ok"
    assert resp.provider == "anthropic"


def test_anthropic_provider_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    secrets = SecretsManager(env={})
    registry = ModelRegistry(secrets=secrets)
    with pytest.raises(Namel3ssError):
        registry.register_model("claude", "anthropic:claude-3-opus")
