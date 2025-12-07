# Announcing Namel3ss V3

Namel3ss V3 is an AI-native programming language and agent OS that makes “write in English → deploy anywhere” real. It pairs a concise DSL with a runtime that ships agents, flows, RAG, memory, plugins, deployment targets, and an optimizer that learns from your traces.

## Why it matters
- Build AI apps with flows, agents, tools, and RAG as first-class citizens.
- Deploy to server, worker, Docker, or Lambda with one command.
- Extend via plugins; observe via metrics/traces; harden with the optimizer.

## What’s new in V3
- Agents V3 (planning, reflection, retries, teams)
- Flows V3 (branching, parallel, error boundaries, triggers)
- RAG V3 (hybrid/cross-store, rewriting, reranking)
- Plugins V3 (manifests + SDK)
- Deployment V3 (server/worker/Docker/Lambda + desktop/mobile skeletons)
- Optimizer (self-improving runtime, overlays)
- Studio + VS Code extension for day-to-day work

## Get started
- Install: `pip install namel3ss` (or `pip install -e .[dev]` for contributors)
- Scaffold: `n3 init app-basic my-app`
- Run: `n3 serve --dry-run` then open Studio.
- Explore examples in `examples/` and templates in `templates/`.

Join us in building adaptive AI systems with a stable, observable, and extensible platform.
