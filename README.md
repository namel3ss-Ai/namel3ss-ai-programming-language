# Namel3ss V3 — AI-Native Programming Language & Agent OS

Namel3ss V3 is an opinionated, AI-native DSL and runtime that treats models, agents, tools, flows, memory, RAG, UI, and distributed execution as first-class concepts.

## Why it exists
- Compose AI systems with a concise, English-like DSL and strong optional typing.
- Run the same program locally or on background workers without rewriting it.
- Ship with batteries included: agents, tools, flows, memory, RAG, UI schema, observability, security.
- Keep behavior inspectable via metrics, traces, and a studio backend.

## Tiny taste of the DSL
```
app "support":
  entry_page "home"
page "home":
  route "/"
  section "hero":
    component "text":
      value "Welcome to Namel3ss"
model "default":
  provider "openai:gpt-4.1-mini"
ai "summarise":
  model "default"
  input from user_message
flow "pipeline":
  step "call":
    kind "ai"
    target "summarise"
```

## What’s implemented in this repo
- Stable lexer/parser/AST/IR for apps, pages, models, ai, agents, memory, flows, plugins, and UI sections/components.
- Runtime engines: model router (dummy + OpenAI), agents (teams, reflection, retries), flows V3 (branching, parallel joins, error boundaries, shared state), tools, memory, RAG V3 (hybrid retrieval, reranking), job queue/worker/scheduler, triggers/automations.
- UI runtime + validation + event router + RAG upload pipeline; Studio React app with panels for pages, traces, metrics, jobs, RAG, flows/automations, plugins, optimizer.
- Plugins V3: manifests, semver compatibility, registry + SDK, HTTP + CLI management.
- Deployment targets V3: server/worker entrypoints, Dockerfile generation, AWS Lambda adapter, desktop/mobile skeletons, CLI `n3 build-target ...`.
- Optimizer (self-improving runtime): heuristic + optional AI-assisted analyzers, overlays, storage, CLI/HTTP/Studio integration.
- Observability + security: tracing across subsystems, metrics, API key auth, RBAC.
- Diagnostics engine, packaging/bundles, and CLI/HTTP surfaces for everything above.

## Getting started (dev)
1. Clone the repo.
2. Install Python 3.11+ and dependencies: `pip install -e .[dev]` (or your preferred tooling).
3. Run tests with coverage: `n3 test-cov` (or `python -m pytest` for a quick run). Use `pytest -m "not slow"` to skip stress tests.
4. Start the server: `python -m namel3ss.server` or `n3 serve --dry-run` to validate config.
5. Scaffold: `n3 init app-basic my-app` (templates in `templates/`). Examples live under `examples/`.
6. Try the CLI: `n3 parse examples/getting_started/app.ai`, `n3 run support --file examples/getting_started/app.ai`, `n3 optimize scan`, or build deploy assets with `n3 build-target server --file examples/getting_started/app.ai --output-dir build/`.
7. Studio: install Node 18+, run `npm install` then `npm run dev` inside `studio/` to open the panels. VS Code users can install the `vscode-extension/` locally for syntax + parse/diagnostics commands.

Read the architecture + API surface → `docs/architecture.md` and `docs/api-surface.md`
