# HTTP API Reference

Core endpoints (all require `X-API-Key`, RBAC enforced):

- Parse / IR / UI: `POST /api/parse`, `/api/run-app`, `/api/run-flow`, `/api/pages`, `/api/page-ui`, `/api/meta`
- Diagnostics / Bundles: `POST /api/diagnostics`, `/api/bundle`
- Jobs: `POST /api/job/flow`, `GET /api/job/{job_id}`, `GET /api/jobs`, `POST /api/worker/run-once`
- Metrics/Traces: `GET /api/metrics`, `GET /api/last-trace`, `GET /api/studio-summary`
- RAG: `POST /api/rag/query`, `POST /api/rag/upload`
- Triggers: `POST /api/flows`, `GET /api/flows/triggers`, `POST /api/flows/triggers`, `POST /api/flows/trigger/{id}`, `POST /api/flows/triggers/tick`
- Plugins: `GET /api/plugins`, `POST /api/plugins/{id}/load`, `/unload`, `/install`
- Optimizer: `GET /api/optimizer/suggestions`, `POST /api/optimizer/scan`, `/apply/{id}`, `/reject/{id}`, `/overlays`
- UI events: `POST /api/ui/event`

## Formatting

- `POST /api/fmt/preview`  
  Preview formatting for Namel3ss `.ai` source.

  **Request body:**
  ```json
  { "source": "<string>" }
  ```

  **Response body:**
  ```json
  { "formatted": "<string>", "changes_made": true | false }
  ```

  Uses the same formatter as the `n3 fmt` CLI command without writing to disk.

## Plugins

- `GET /api/plugins`  
  Returns a list of loaded Namel3ss plugins and their metadata.

  **Response body:**
  ```json
  {
    "plugins": [
      {
        "id": "example-plugin",
        "name": "Example Plugin",
        "version": "1.0.0",
        "description": "Short description",
        "entrypoints": {},
        "tags": []
      }
    ]
  }
  ```

## Studio

- `GET /studio` — Serves the minimal Namel3ss Studio HTML UI.
- `GET /studio-static/...` — Serves Studio CSS and JS assets used by `/studio`.

## Traces

- `GET /api/traces` — Returns a list of recent traces with basic metadata (id, flow name, timestamps, status, duration).
- `GET /api/trace/{trace_id}` — Returns the full trace payload (graph, events, timing, costs) for a given trace id.

## Agent Traces

- `GET /api/agent-traces` — Returns a list of recent agent runs with basic metadata (id, agent name, team, role, status, timing, cost).
- `GET /api/agent-trace/{trace_id}` — Returns full details for a given agent run, including steps, tool calls, memory and RAG events, and reasoning messages when available.

See `docs/api-surface.md` for the stable surface contract. Unauthorized requests return 401; insufficient role returns 403.
