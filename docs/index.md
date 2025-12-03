# Namel3ss V3

Namel3ss is an AI-native programming language and agent OS. It combines a concise DSL with a runtime that ships agents, flows, RAG, memory, plugins, deployment, and an optimizer for self-improving apps.

## What you get
- Stable DSL → AST → IR → runtime graph (no grammar changes in V3).
- AI layer (dummy + OpenAI), Agents V3, Flows V3 (branching/parallel/error boundaries), RAG V3 (hybrid + cross-store), memory + jobs, plugins, deployment targets, Studio UI, optimizer.
- Security and observability by default (API key + RBAC, tracing, metrics).

## Stability Promise
Public surfaces (CLI commands listed in docs/api-surface.md, HTTP endpoints in docs/reference/http-api.md, and Plugin/Deployment/Optimizer APIs) are stable for 12 months starting from v3.0.0. Bug fixes may be shipped, but breaking changes will be deferred to a future major version or announced with migration notes.

## Getting started fast
- Install: `pip install -e .[dev]`
- Explore templates: `n3 init app-basic my-app`
- Run your first app: `n3 serve --dry-run` then hit the Studio.
- Read the quickstart guides under docs/quickstart/.
