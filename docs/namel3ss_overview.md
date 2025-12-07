# Namel3ss V3 — Architecture Overview

## 1. What is Namel3ss V3?
Namel3ss V3 is an AI-native programming language and runtime that treats AI models, agents, tools, RAG, and UI as first-class concepts. It combines an English-like DSL with strong optional typing, a composable runtime, and a distributed execution model so apps can move from local runs to background workers without changing source.

## 2. Mental Model
- **Language (DSL):** Declarative, English-style syntax for apps, pages, flows, agents, models, memory, plugins, and UI components. Legacy syntax is auto-transformed but discouraged.
- **Runtime (engine + context):** Executes IR, builds graphs, and orchestrates AI, agents, flows, tools, memory, and RAG.
- **AI platform:** ModelRegistry + ModelRouter, dummy provider today, cost-aware hooks via MetricsTracker.
- **Workflow system:** Flows, jobs, workers, scheduler, async helpers for background execution.
- **UI schema:** Page sections/components rendered into a portable UI tree.
- **Observability + studio:** Traces, metrics, and a StudioEngine for summaries.

## 3. Language Concepts
- **app / page**
  - Declare routes, metadata, and UI sections/components.
  - Example:
    ```
    app "support":
      entry_page "home"
    page "home":
      route "/"
      section "hero":
        component "text":
          value "Welcome"
    ```
- **model + ai**
  - Models are logical names bound to providers; `ai` blocks define callable prompts/inputs.
  - Example:
    ```ai
    model "default":
      provider "openai:gpt-4.1-mini"
    ai "summarise":
      model "default"
      input from "user_input"
    ```
- **agent + Agent Teams**
  - Agents have goals/personalities; AgentRunner/TeamRunner execute AI/tool steps with retries and team roles.
- **memory**
  - Declared memory spaces; runtime uses ShardedMemoryEngine for distribution.
- **flow**
  - Sequential orchestration over ai/agent/tool steps.
- **plugin**
  - Declarative plugin entries with optional descriptions for integration readiness.

## 4. Runtime Architecture
- Pipeline: **AST → IR → RuntimeEngine → Graph → Execution**
- **ExecutionContext** carries:
  - ModelRouter + providers
  - ShardedMemoryEngine
  - RAGEngine + RAGSyncWorker
  - ToolRegistry
  - AgentRunner + AgentTeamRunner
  - FlowEngine
  - SecretsManager
  - MetricsTracker
  - Tracer

```
DSL → Lexer/Parser → AST → IR → Engine
                          │
            ┌ Graph ──────┼─ UI Renderer
            │             │
        ModelRouter   FlowEngine
        AgentRunner   ToolRegistry
        Memory/RAG    Metrics/Tracer
```

## 5. Distributed & Jobs
- **Job model:** flow/agent/page/tool targets with status/result/error fields.
- **JobQueue:** in-memory queue with enqueue/get/list.
- **Worker:** polls queue, builds runtime, executes jobs, updates status and traces.
- **Scheduler:** helpers to enqueue flow/agent/page jobs.
- **APIs/CLI:** `/api/job/...` endpoints and `n3 job-*` commands for submission/status.

## 6. Observability & Studio
- **Tracing:** AI, page, app, agent, flow, team, job, and UI section counts.
- **Metrics:** cost/usage events per AI/tool/agent/flow via MetricsTracker.
- **StudioEngine:** builds dashboard summaries from IR, jobs, tracer, memory, and RAG; exposed via `/api/studio-summary`.
- **APIs:** `/api/metrics`, `/api/last-trace`, `/api/meta` surface metrics, traces, and model/plugin metadata.

## 7. Security
- API key auth via `X-API-Key`.
- Roles: **Admin**, **Developer**, **Viewer** with RBAC checks on server endpoints.

## 8. Server & CLI Surface
- **HTTP (FastAPI) highlights:**
  - `/health` — liveness
  - `/api/parse`, `/api/run-app`, `/api/run-flow`
  - `/api/pages`, `/api/page-ui`
  - `/api/metrics`, `/api/studio-summary`, `/api/last-trace`, `/api/meta`
  - `/api/diagnostics`, `/api/bundle`
  - `/api/job/flow`, `/api/job/agent`, `/api/job/{id}`
- **CLI (n3) highlights:**
  - `parse`, `ir`, `run`, `graph`, `serve`
  - `run-agent`, `run-flow`, `page-ui`, `meta`
  - `job-flow`, `job-agent`, `job-status`
  - `diagnostics`, `bundle`

## 9. Current Status & Roadmap
- **What works today**
  - DSL → AST → IR with app/page/ai/model/agent/memory/flow/plugin/UI sections
  - Runtime graph + execution for pages, agents, flows
  - Model routing over registry + dummy provider
  - Sharded memory engine, RAG engine, sync worker
  - Tools/built-ins, agent runner, agent teams
  - Distributed jobs (queue, worker, scheduler) + job APIs/CLI
  - UI renderer + page/UI endpoints
  - Observability traces, metrics, diagnostics, studio summary
  - Security (API keys, RBAC)
- **Planned next**
  - Real provider integrations and richer cost models
  - Better RAG indexing/deduplication and external stores
  - Persistent storage for memory/jobs
  - Richer UI components and client rendering
  - More diagnostics rules and bundle/deploy targets
