# Logging and privacy

To reduce leakage risk, Namel3ss redacts prompts and sensitive metadata by default.

- Prompts/messages are replaced with `[REDACTED]` in event logs when `N3_LOG_REDACT_PROMPTS` is unset or `true`.
- Metadata keys such as `email`, `phone`, `authorization`, `access_token`, `password`, `secret`, `token` are masked when `N3_LOG_REDACT_METADATA` is unset or `true`.
- Override (for debugging only):
  - `N3_LOG_REDACT_PROMPTS=false`
  - `N3_LOG_REDACT_METADATA=false`

Warnings:
- Disabling redaction in production can leak PII or secrets into logs. Prefer enabling redaction and using lower log verbosity (e.g., INFO).
- Ensure downstream log sinks (e.g., ELK, CloudWatch) have appropriate access controls and retention policies.
