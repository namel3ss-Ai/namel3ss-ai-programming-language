# API Surface (RC1)

## CLI (n3)
- parse, ir, run, graph, serve
- run-agent, run-flow, page-ui, meta
- diagnostics, lint, bundle, build/build-target (server/worker/docker/serverless-aws/serverless-cloudflare/desktop/mobile)
- job-flow, job-agent, job-status
- optimize (scan, list, apply, reject, overlays)
- test-cov (pytest with coverage)

## HTTP
- Health: `GET /health`
- Parse/IR/UI: `POST /api/parse`, `/api/run-app`, `/api/run-flow`, `/api/pages`, `/api/page-ui`, `/api/meta`
- Diagnostics/Bundles: `POST /api/diagnostics`, `/api/bundle` (diagnostics can include lint when requested)
- Jobs: `POST /api/job/flow`, `GET /api/job/{job_id}`, `GET /api/jobs`, `POST /api/worker/run-once`
- Metrics/Traces: `GET /api/metrics`, `GET /api/last-trace`, `GET /api/studio-summary`
- RAG: `POST /api/rag/query`, `POST /api/rag/upload`
- Triggers/Flows: `POST /api/flows`, `GET /api/flows/triggers`, `POST /api/flows/triggers`, `POST /api/flows/trigger/{id}`, `POST /api/flows/triggers/tick`
- Plugins: `GET /api/plugins`, `POST /api/plugins/{id}/load`, `/api/plugins/{id}/unload`, `/api/plugins/install`
- Optimizer: `GET /api/optimizer/suggestions`, `POST /api/optimizer/scan`, `/api/optimizer/apply/{id}`, `/api/optimizer/reject/{id}`, `/api/optimizer/overlays`
- UI events: `POST /api/ui/event`

All sensitive endpoints enforce `X-API-Key` and RBAC (Admin/Developer/Viewer).
