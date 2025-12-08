# Providers & API Keys (18A)

Namel3ss now has a unified, explicit provider configuration with friendly diagnostics for missing or invalid API keys.

## Configure providers

Create `namel3ss.config.json` at your project root:

```json
{
  "providers": {
    "openai_default": {
      "type": "openai",
      "api_key_env": "OPENAI_API_KEY",
      "model_default": "gpt-4.1-mini"
    },
    "gemini_default": {
      "type": "gemini",
      "api_key_env": "GEMINI_API_KEY"
    }
  },
  "default": "openai_default"
}
```

Environment variables can override or supply keys:

- `OPENAI_API_KEY` / `N3_OPENAI_API_KEY`
- `GEMINI_API_KEY` / `N3_GEMINI_API_KEY`
- `ANTHROPIC_API_KEY` / `N3_ANTHROPIC_API_KEY`

If a key exists in the environment, Namel3ss auto-creates a sensible `openai_default` provider so new projects work with minimal setup.

## Use providers in AI calls

```ai
ai is "support_bot":
  provider is "openai_default"   # optional if default is set
  model is "gpt-4.1-mini"
  system is "You are a helpful agent."
```

If `provider` is omitted, the global default from `namel3ss.config.json` is used. If no default exists, compilation fails with `N3L-1800`.

## Diagnostics

- `N3L-1800`: AI references an unknown provider name.
- `N3P-1801`: Provider is missing an API key. Message tells you which env var to set.
- `N3P-1802`: Provider rejected the API key (401/403 unauthorized).

Errors flow back through runtime responses and Studio so issues are immediately visible.

## Studio provider status

Studio polls `/api/providers/status` and shows a compact indicator:

- ✅ OK
- ⚠️ Missing API key
- ❌ Unauthorized

Clicking through to the documentation from the warning helps quickly fix setup issues.
