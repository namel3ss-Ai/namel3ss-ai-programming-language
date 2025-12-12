# Testing & Coverage

- Default command: `python -m pytest` (configured via `pyproject.toml`).
- Coverage: `n3 test-cov` or `pytest --cov=namel3ss --cov-report=term-missing`.
- Markers:
  - `unit`: fast tests
  - `integration`: multi-component tests
  - `slow`: stress/load (e.g., parallel flows, heavy RAG)
  - `e2e`: end-to-end (reserved)
- Skip slow tests by default with `pytest -m "not slow"`.
- No external network is required; OpenAI calls are stubbed; SQLite is used where persistence is needed.
