# Adding providers to the model registry

Namel3ss decouples logical model names from concrete provider implementations.

## Registering provider configs

Use the `ModelRegistry.register_provider_config` API to add or override providers at runtime:

```python
from namel3ss.ai.registry import ModelRegistry
from namel3ss.config import ProviderConfig

registry = ModelRegistry()
registry.register_provider_config(
    "my_dummy",
    ProviderConfig(type="dummy", model_default="gpt-echo"),
    set_default=True,  # optional
)
registry.register_model("support_bot", "my_dummy")
```

- `ProviderConfig` fields:
  - `type`: provider family (`openai`, `anthropic`, `azure_openai`, `gemini`, `ollama`, `lmstudio`, `http_json`, `dummy`, etc.).
  - `api_key` / `api_key_env`: credentials (if required).
  - `base_url`: override endpoint.
  - `model_default`: default model/deployment for the provider.
  - `extra`: provider-specific options (API version, headers, etc.).

## Routing

- Logical model names in `.ai` files map to provider configs via `ModelRegistry` and `ModelRouter`.
- You can set a default provider in config (e.g., `providers.default` in `namel3ss.config`) or via `set_default=True` when registering a provider config.
- `ModelRouter` resolves logical names to providers and supports fallback providers defined in the global AI config.

This extension surface allows teams to plug in custom or proprietary providers without modifying core engine code.
