# Installation

1. **Python 3.11+**: ensure it is available on PATH.
2. **Install deps**: `pip install namel3ss` (use `pip install -e .[dev]` only when developing this repo)
3. **Studio (optional)**: inside `studio/` run `npm install`.
4. **API keys**: set `OPENAI_API_KEY` if you want real model calls. Otherwise the deterministic dummy provider is used.
5. **Run tests**: `n3 test-cov` or `pytest -m "not slow"`.

Environment flags:
- `N3_MODEL_<NAME>_PROVIDER` (dummy|openai|http_json)
- `N3_MODEL_<NAME>_MODEL` (provider-specific model id)
- `N3_MODEL_<NAME>_BASE_URL` / `N3_MODEL_<NAME>_RESPONSE_PATH` for http_json endpoints (Ollama/LM Studio/etc.)
- Embeddings: `N3_EMBEDDINGS_PROVIDER` (deterministic|openai|http_json), `N3_EMBEDDINGS_MODEL`, `N3_EMBEDDINGS_BASE_URL`, `N3_EMBEDDINGS_RESPONSE_PATH`
- `N3_PLUGINS_DIR` (default `plugins`) for plugin discovery.
- `N3_OPTIMIZER_DB` / `N3_OPTIMIZER_OVERLAYS` to control optimizer persistence locations.
