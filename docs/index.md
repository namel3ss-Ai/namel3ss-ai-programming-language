# Namel3ss

Namel3ss is an AI-native programming language and agent OS. It pairs a concise DSL with a runtime that covers models, agents, flows, tools, memory, RAG, security, observability, plugins, and the optimizer so you can ship production AI systems quickly.

## What you get
- Stable DSL, AST, and IR powering apps, pages, agents, flows, memory, and RAG.
- AI stack with multi-provider routers, retrieval pipelines, and memory/RAG fusion.
- Agents 2.0 (reflection, debate, planning, evaluation) and Flows 2.0 (parallel, for_each, try/catch/finally, timeouts, metrics).
- Memory 2.0 (episodic/semantic, retention, summarization worker) plus observability and security by default.
- Optimizer++, plugins/marketplace, examples catalog, templates, Studio UI, and deployment targets.

## Stability Promise
Public surfaces (CLI commands, HTTP endpoints, Plugin/Deployment/Optimizer APIs) are stable for the 3.0.x line. Bug fixes may be shipped, but breaking changes will be announced with migration notes.

## Getting started fast
- Install: `pip install namel3ss` (use `pip install -e .[dev]` when hacking on this repo)
- Explore templates: `n3 init app-basic my-app`
- Run your first app: `n3 serve --dry-run` then open Studio.
- Read the quickstart guides under `docs/quickstart/`.
- Deep dive: see the Learn Namel3ss book in `docs/book/`.
