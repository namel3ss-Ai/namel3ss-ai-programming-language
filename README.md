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
- Full lexer/parser/AST/IR for apps, pages, models, ai, agents, memory, flows, plugins, and UI sections/components.
- Runtime engine with model routing, sharded memory engine, RAG engine + sync worker, tools, agents (including teams), flows, and distributed job queue/worker/scheduler.
- UI renderer and endpoints for pages/UI.
- Observability: traces across AI/page/app/agent/flow/team/jobs + metrics tracking.
- Security: API key auth + RBAC.
- Studio summary, diagnostics engine, packaging/bundles, and CLI/HTTP surfaces for everything above.

## Getting started (dev)
1. Clone the repo.
2. Install Python 3.11+ and dependencies: `pip install -e .[dev]` (or your preferred tooling).
3. Run tests: `python -m pytest`.
4. Start the server: `python -m namel3ss.server` (or `n3 serve --dry-run` to verify config).
5. Try the CLI: `n3 parse examples/app.ai` or run an app: `n3 run support --file examples/app.ai`.

Read the full architecture overview → `docs/namel3ss_v3_overview.md`
