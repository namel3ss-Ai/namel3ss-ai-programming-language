# Chapter 11 — Providers & API Configuration

- **Config:** Set providers via config file or environment. Example (`namel3ss.config.json`):
```json
{
  "providers": {
    "openai_default": {
      "type": "openai",
      "api_key_env": "OPENAI_API_KEY",
      "model_default": "gpt-4.1-mini"
    }
  },
  "default": "openai_default"
}
```
- **Selection:** Per-model `provider` or per-AI override; falls back to default.
- **Errors:** Unknown provider `N3L-1800`; missing key `N3P-1801`; unauthorized `N3P-1802`.
- **Status:** `/api/providers/status` powers Studio’s provider status indicator.

Cross-reference: parser provider fields in `src/namel3ss/parser.py`; runtime config loading `src/namel3ss/config.py`, routing in `src/namel3ss/ai/registry.py` and `src/namel3ss/ai/router.py`, providers in `src/namel3ss/ai/providers/*`; tests `tests/test_providers_config.py`; examples: any AI block with `provider` set.
