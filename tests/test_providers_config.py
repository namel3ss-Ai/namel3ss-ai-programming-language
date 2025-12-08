import json
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.config import ProviderConfig, ProvidersConfig, load_config
from namel3ss.errors import ProviderAuthError, ProviderConfigError
from namel3ss.ir import IRAiCall
from namel3ss.runtime.context import ExecutionContext, execute_ai_call_with_registry
from namel3ss.server import create_app
from namel3ss.secrets.manager import SecretsManager
from namel3ss.ai.registry import ModelConfig


def test_load_config_from_file(tmp_path, monkeypatch):
    cfg_path = tmp_path / "namel3ss.config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "providers": {
                    "openai_default": {"type": "openai", "api_key_env": "OPENAI_API_KEY", "model_default": "gpt-4.1-mini"}
                },
                "default": "openai_default",
            }
        )
    )
    monkeypatch.chdir(tmp_path)
    cfg = load_config(env={})
    assert cfg.providers_config.default == "openai_default"
    assert "openai_default" in cfg.providers_config.providers
    assert cfg.providers_config.providers["openai_default"].api_key_env == "OPENAI_API_KEY"


def test_missing_key_raises_provider_config_error():
    providers_cfg = ProvidersConfig(
        default="openai_default",
        providers={"openai_default": ProviderConfig(type="openai", api_key_env="OPENAI_API_KEY")},
    )
    registry = ModelRegistry(secrets=SecretsManager(env={}), providers_config=providers_cfg)
    router = ModelRouter(registry)
    ai_call = IRAiCall(name="bot", model_name="gpt-4.1-mini", provider="openai_default", input_source="hi")
    ctx = ExecutionContext(app_name="app", request_id="req-1", user_input="hello")
    with pytest.raises(ProviderConfigError) as excinfo:
        execute_ai_call_with_registry(ai_call, registry, router, ctx)
    assert excinfo.value.code == "N3P-1801"


def test_unauthorized_maps_to_provider_auth_error(monkeypatch):
    providers_cfg = ProvidersConfig(
        default="openai_default",
        providers={"openai_default": ProviderConfig(type="openai", api_key="bad-key")},
    )
    registry = ModelRegistry(secrets=SecretsManager(env={}), providers_config=providers_cfg)
    router = ModelRouter(registry)
    # Pre-create and patch provider client to force 401
    provider = registry._create_provider(ModelConfig(name="temp", provider="openai_default", model="gpt-4.1-mini"))

    def fail_client(url, body, headers):
        raise HTTPError(url, 401, "unauthorized", hdrs=None, fp=None)

    provider._http_client = fail_client  # type: ignore[attr-defined]
    ai_call = IRAiCall(name="bot", model_name="gpt-4.1-mini", provider="openai_default", input_source="hi")
    ctx = ExecutionContext(app_name="app", request_id="req-1", user_input="hello")
    with pytest.raises(ProviderAuthError) as excinfo:
        execute_ai_call_with_registry(ai_call, registry, router, ctx)
    assert excinfo.value.code == "N3P-1802"


def test_provider_status_endpoint(tmp_path, monkeypatch):
    cfg_path = tmp_path / "namel3ss.config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "providers": {
                    "openai_default": {"type": "openai", "api_key": "dummy"},
                    "gemini_default": {"type": "gemini", "api_key_env": "GEMINI_API_KEY"},
                },
                "default": "openai_default",
            }
        )
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    ModelRegistry.last_status["openai_default"] = "unauthorized"
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/providers/status", headers={"X-API-Key": "viewer-key"})
    assert resp.status_code == 200
    data = resp.json()
    providers = {p["name"]: p for p in data["providers"]}
    assert providers["openai_default"]["last_check_status"] == "unauthorized"
    assert providers["openai_default"]["has_key"] is True
    assert providers["gemini_default"]["has_key"] is False
