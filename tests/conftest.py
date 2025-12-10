import json

import pytest


@pytest.fixture(autouse=True)
def _dummy_providers(monkeypatch):
    """Ensure tests always have a stub provider configuration."""
    payload = {
        "default": "openai_default",
        "providers": {
            "openai_default": {
                "type": "dummy",
                "api_key": "test-key",
            }
        },
    }
    monkeypatch.setenv("N3_PROVIDERS_JSON", json.dumps(payload))
    yield
