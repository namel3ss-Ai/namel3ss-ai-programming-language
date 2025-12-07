import pytest

from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ai.providers.azure_openai import AzureOpenAIProvider
from namel3ss.errors import Namel3ssError
from namel3ss.secrets.manager import SecretsManager


def test_azure_provider_success():
    secrets = SecretsManager(env={"AZURE_OPENAI_API_KEY": "sk-azure", "AZURE_OPENAI_BASE_URL": "https://example.azure.com"})
    registry = ModelRegistry(secrets=secrets)
    registry.register_model("azure-model", "azure_openai:my-deployment")
    provider: AzureOpenAIProvider = registry.get_provider_for_model("azure-model")  # type: ignore[assignment]

    def fake_client(url, body, headers):
        assert "api-version" in url
        assert "api-key" in headers
        return {"choices": [{"message": {"content": "hi"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    provider._http_client = fake_client  # type: ignore[attr-defined]
    router = ModelRouter(registry, secrets=secrets)
    resp = router.generate(messages=[{"role": "user", "content": "ping"}], model="azure-model")
    assert resp.text == "hi"
    assert resp.provider == "azure_openai"


def test_azure_provider_missing_key():
    secrets = SecretsManager(env={"AZURE_OPENAI_BASE_URL": "https://example.azure.com"})
    registry = ModelRegistry(secrets=secrets)
    with pytest.raises(Namel3ssError):
        registry.register_model("azure-model", "azure_openai:my-deployment")
