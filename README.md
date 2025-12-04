# Namel3ss — AI-Native Programming Language & Agent OS

Namel3ss is a DSL and runtime for building AI-native applications. It treats models, agents, flows, tools, memory, RAG, security, observability, and optimization as first-class concepts so you can ship production-ready AI systems quickly.

## Highlights
- **AI stack**: Multi-provider model and embeddings routers, retrieval pipelines, and memory/RAG fusion.
- **Agents 2.0**: Reflection, debate, planning, evaluation, and team runners with memory hooks.
- **Flows 2.0**: Parallel/for_each/try-catch/finally, timeouts, and per-step metrics.
- **Memory 2.0**: Episodic + semantic memories, retention, summarization worker, and fused recall.
- **Security 2.0**: OAuth/API keys, RBAC, field-level masking, quotas.
- **Observability**: Tracing, correlated logs, metrics, and observability APIs for Studio.
- **Optimizer++**: Evaluation harness, suggestion engine, history with accept/reject loop.
- **Ecosystem**: Plugin manifests/registry + SDK, curated examples catalog, Studio panels, and templates.

## Quickstart
1. Install (Python 3.11+):  
   `pip install -e .[dev]`
2. Run tests (fast suite):  
   `python -m pytest -m "not slow" -q -o addopts=''`
3. Explore an example:  
   `n3 parse examples/getting_started/app.ai`  
   `n3 run support --file examples/getting_started/app.ai`
4. Start the server + Studio backend:  
   `python -m namel3ss.server` (or `n3 serve --dry-run` to validate config)
5. Browse examples under `examples/` and plugins under `plugins/` to extend the runtime.

## Documentation & Links
- Docs site (MkDocs): `docs/index.md` (build with `mkdocs build --strict`)
- Architecture & API surface: `docs/architecture.md`, `docs/api-surface.md`
- Quickstart guides: `docs/quickstart/`
- Reference: CLI, HTTP API, plugins, optimizer under `docs/reference/`
- Release notes: `CHANGELOG.md` and `docs/releases/`
- Migration guidance: `MIGRATING.md`

## Contributing
Pull requests are welcome. Please run the fast test suite (`pytest -m "not slow"`) and keep docs up to date. For feature additions, ensure observability, security, and ecosystem considerations are covered.
