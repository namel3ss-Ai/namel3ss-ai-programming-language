# Deployment

Targets built via `n3 build-target <target> --file <file> --output-dir <dir>`:
- `server`: FastAPI ASGI entry (`namel3ss.deploy.server_entry:app`).
- `worker`: background worker entry.
- `docker`: Dockerfiles for server/worker (multi-stage).
- `serverless-aws`: Lambda zip with ASGI adapter handler.
- `serverless-cloudflare`: Cloudflare Worker bundle (worker.js + wrangler.toml).
- `desktop` / `mobile`: emits ready-to-customize bundles/configs for Tauri/Expo targets.

Artifacts are deterministic and filesystem-only; no network is required during build.

## Simple build commands

Friendly wrappers:

```
n3 build desktop
n3 build desktop app.ai
n3 build mobile
n3 build serverless-aws app.ai --output-dir build/aws
```

Defaults:
- If no file is provided, uses `app.ai` or the single `.ai` file in the current directory.
- Output directories default to `build/<target>` (desktop → `build/desktop`, mobile → `build/mobile`).
- Under the hood this delegates to `build-target` and DeployBuilder; `build-target` remains available for explicit CI usage.

## Cloudflare Serverless

Build:

```
n3 build-target serverless-cloudflare --file app.ai --output-dir build/cloudflare
```

Outputs:
- `app.ai`
- `worker.js` (Cloudflare entry with optional forwarding to `N3_ORIGIN`)
- `wrangler.toml` (configure account_id, routes, compatibility_date as needed)
- `README.md` with quick start tips

Workflow:
- Install Wrangler CLI.
- Configure `account_id`/routes/env vars in `wrangler.toml`.
- Run locally: `wrangler dev`
- Deploy: `wrangler publish`

## Runtime Phase FT — File-Based Flow Triggers

Define triggers in your `.ai` code:

```
trigger "import_new_files":
  kind "file"
  path "uploads/"
  pattern "*.csv"
  flow "process_csv_file"
```

Notes:
- `path` must point to an existing directory (absolute or project-relative).
- `pattern` is a glob (defaults to `*`).
- Optional `include_content: true` includes file text for small files (<10 MB).
- Events: created, modified, deleted.
- Payload delivered to flows:
  `{"trigger_id": "...", "trigger_kind": "file", "event": "created", "file": "<path>", "content": "..."}`
