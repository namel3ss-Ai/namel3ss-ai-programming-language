# Secrets management

Namel3ss uses a pluggable `SecretsManager` abstraction. The default backend is environment-based:

- `EnvSecretsManager` reads secrets from environment variables (optionally with a prefix).
- `get_default_secrets_manager()` returns the env-backed manager; future backends (e.g., Vault/KMS) can be hooked via `N3_SECRETS_BACKEND` (currently only `env` is supported).

Common provider secrets:
- `N3_OPENAI_API_KEY` / `OPENAI_API_KEY`
- `N3_ANTHROPIC_API_KEY` / `ANTHROPIC_API_KEY`
- `N3_GEMINI_API_KEY` / `GEMINI_API_KEY`
- `N3_AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_API_KEY`
- Generic HTTP providers: set `api_key_env` in `namel3ss.config` or supply `N3_PROVIDER_<NAME>_*` env vars.

Guidelines:
- Inject secrets via your platform’s secret store (Kubernetes Secrets, AWS Secrets Manager, etc.) into environment variables.
- Avoid hard-coding secrets in `.ai` files or configs.
- Use `require_secret` for mandatory keys to surface clear errors when missing.
