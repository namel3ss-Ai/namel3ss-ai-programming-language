# Namel3ss V3 Architecture (RC1)

- **Language pipeline**: lexer → parser → canonical AST → IR (apps, pages, ai, agents, flows, memory, datasets/frames, plugins, UI components). Legacy syntax is auto-transformed to the modern surface; grammar is stable.
- **Runtime**:
  - ModelRouter (dummy + OpenAI + Gemini + HTTP) with tracing/metrics; streaming/JSON-mode where supported.
  - Agents (planning, reflection/evaluation, retries, teams/voting).
  - Flows (FlowGraph/FlowNode/FlowState, branching, parallel joins, error boundaries, shared state, tracing/metrics).
  - Tools registry; RAG (hybrid dense/sparse, reranking, rewriting, metrics/traces); memory engines (in-memory + SQLite).
  - Jobs: queue, scheduler, worker; triggers/automations (schedule/http/memory/agent-signal/file) enqueue flows.
  - UI runtime: components, validation, UIEventRouter dispatch to flows/agents/tools, RAG upload pipeline.
  - Plugins: manifests (TOML), semver compatibility, registry + SDK to register tools/agents/flows/RAG/memory/components.
  - Deployment: builder outputs server/worker entrypoints, Dockerfiles, AWS Lambda zip, Cloudflare worker bundle, desktop/mobile configs.
  - Optimizer: heuristic + optional AI-assisted analyzers over metrics/traces/memory; suggestions persisted; overlays applied at runtime.
- **Observability & Security**: tracer spans for AI/pages/apps/agents/flows/teams/jobs/RAG/UI, metrics tracker, API key auth + RBAC.
- **Studio**: React app with panels for pages, runner, traces, metrics, jobs, RAG/memory, diagnostics, flows/automations, plugins, optimizer.
