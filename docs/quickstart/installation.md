# Installation

1. **Python 3.11+**: ensure it is available on PATH.
2. **Install deps**: `pip install -e .[dev]`
3. **Studio (optional)**: inside `studio/` run `npm install`.
4. **API keys**: set `OPENAI_API_KEY` if you want real model calls. Otherwise the deterministic dummy provider is used.
5. **Run tests**: `n3 test-cov` or `pytest -m "not slow"`.

Environment flags:
- `N3_PLUGINS_DIR` (default `plugins`) for plugin discovery.
- `N3_OPTIMIZER_DB` / `N3_OPTIMIZER_OVERLAYS` to control optimizer persistence locations.
