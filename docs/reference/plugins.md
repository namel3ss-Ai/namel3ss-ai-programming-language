# Plugins Reference

- Manifests: `plugin.toml` with `id`, `name`, `version`, `n3_core_version`, `entrypoints`.
- Compatibility: semver ranges checked against core version (3.0.0).
- Registry: plugins live under `N3_PLUGINS_DIR` (default `plugins/`). Discovery + auto-load occurs at runtime.
- Entry points get a `PluginSDK` with sub-SDKs for tools, agents, flows, RAG, memory.

Default plugins shipped:
- `default-tools`: http_get, get_time, math_eval.
- `default-rag`: registers a default in-memory index.
- `default-agents`: registers a simple summarizer agent.

CLI/HTTP management:
- `n3 plugins` via `n3 meta` or load/unload with API: `/api/plugins`, `/api/plugins/{id}/load|unload|install`.
