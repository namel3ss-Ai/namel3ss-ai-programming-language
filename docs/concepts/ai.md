# AI & Model Routing

Namel3ss routes AI calls through a configurable ModelRouter. Models declared in DSL map to runtime configs sourced from environment variables.

Providers:
- `dummy` (deterministic, CI-safe)
- `openai` (Chat Completions API; uses `N3_OPENAI_API_KEY` and optional `N3_OPENAI_BASE_URL`)
- `http_json` (generic HTTP POST for Ollama/LM Studio/custom gateways)
- `gemini` (Google Gemini; uses `GEMINI_API_KEY` and optional `GEMINI_BASE_URL`, streaming + JSON mode supported)

Per-model env overrides (uppercase model name):
- `N3_MODEL_<NAME>_PROVIDER` (dummy | openai | http_json)
- `N3_MODEL_<NAME>_MODEL` (model id for provider)
- `N3_MODEL_<NAME>_BASE_URL` (for http_json/openai overrides)
- `N3_MODEL_<NAME>_RESPONSE_PATH` (dot path for http_json response extraction)

Requests are message-based (`messages=[{"role": "...", "content": "..."}]`); streaming is supported by providers that expose it (OpenAI).
Gemini supports streaming and JSON-mode; toggle JSON-mode via the caller (e.g., agent/flow config) the same way you would for OpenAI.
