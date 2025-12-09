# Security hardening guide

Recommended production setup:
- Terminate TLS and validate OAuth2/JWT at an API gateway or reverse proxy (Kong, AWS API Gateway, Envoy, Nginx+OIDC).
- Enforce WAF and rate limiting at the edge; Namel3ss should run behind this boundary as a stateless backend.
- Keep outbound network restricted to known provider/tool endpoints.

Secrets:
- Store provider keys/DB credentials in a secret manager; inject via environment variables (used by `EnvSecretsManager`).
- Never commit secrets into `.ai` files or configs; rotate keys regularly.

Logging:
- Redaction is enabled by default (`N3_LOG_REDACT_PROMPTS`, `N3_LOG_REDACT_METADATA`). Keep it on in production.
- Use production log levels (INFO/ERROR); avoid DEBUG in prod.

Ops/security checklist:
- Rebuild images regularly to pull patched base layers.
- Keep Namel3ss updated to the latest release.
- Validate provider quotas and set conservative concurrency (`N3_MAX_PARALLEL_TASKS`).
- Monitor provider call metrics and circuit status for anomaly detection.
- Ensure backups and retention policies for any stateful backends (DBs/vector stores) are secured.
