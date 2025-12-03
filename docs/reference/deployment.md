# Deployment

Targets built via `n3 build-target <target> --file <file> --output-dir <dir>`:
- `server`: FastAPI ASGI entry (`namel3ss.deploy.server_entry:app`).
- `worker`: background worker entry.
- `docker`: Dockerfiles for server/worker (multi-stage).
- `serverless-aws`: Lambda zip with ASGI adapter handler.
- `desktop` / `mobile`: skeletons (packaging pipeline is future work, raises NotImplementedError if invoked directly).

Artifacts are deterministic and filesystem-only; no network is required during build.
