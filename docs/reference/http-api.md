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

See `docs/api-surface.md` for the stable surface contract. Unauthorized requests return 401; insufficient role returns 403.
