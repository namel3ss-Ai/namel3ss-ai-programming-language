# Namel3ss V3 Architecture (RC1)

- **Language pipeline**: lexer → parser → AST → IR (apps, pages, ai, agents, flows, memory, datasets, indexes, plugins, UI components). Grammar is stable and untouched by runtime changes.
- **Runtime**:
  - ModelRouter (dummy + OpenAI providers) with tracing/metrics.
  - Agents V3 (planning, reflection/evaluation, retries, teams/voting).
  - Flows V3 (FlowGraph/FlowNode/FlowState, branching, parallel joins, error boundaries, shared state, tracing/metrics).
  - Tools registry; RAG V3 (multi-index, hybrid dense/sparse, reranking, rewriting, metrics/traces); memory engines (in-memory + SQLite).
  - Jobs: queue, scheduler, worker; triggers/automations (schedule/http/memory/agent-signal) enqueue flows.
  - UI runtime: runtime components, validation, UIEventRouter dispatch to flows/agents/tools, RAG upload pipeline.
  - Plugins V3: manifests (TOML), semver compatibility, registry + SDK to register tools/agents/flows/RAG/memory/components.
  - Deployment V3: builder outputs server/worker entrypoints, Dockerfiles, AWS Lambda zip, desktop/mobile skeletons.
  - Optimizer: heuristic + optional AI-assisted analyzers over metrics/traces/memory; suggestions persisted; overlays applied at runtime.
- **Observability & Security**: tracer spans for AI/pages/apps/agents/flows/teams/jobs/RAG/UI, metrics tracker, API key auth + RBAC.
- **Studio**: React app with panels for pages, runner, traces, metrics, jobs, RAG/memory, diagnostics, flows/automations, plugins, optimizer.
