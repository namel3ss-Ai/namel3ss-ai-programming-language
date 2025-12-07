# 8. Deployment

## Build targets
Use the friendly build command:
```bash
n3 build desktop
n3 build mobile
n3 build serverless-aws app.ai --output-dir build/aws
n3 build serverless-cloudflare app.ai --output-dir build/cloudflare
```
Or the explicit form: `n3 build-target <target> --file <file> --output-dir <dir>`.

Supported targets:
- `server`, `worker`, `docker`
- `serverless-aws` (Lambda zip with ASGI adapter)
- `serverless-cloudflare` (worker.js + wrangler.toml)
- `desktop` (Tauri-ready bundle/config)
- `mobile` (Expo/React Native config)

## Cloudflare example
```bash
n3 build serverless-cloudflare app.ai --output-dir build/cloudflare
cd build/cloudflare
wrangler dev   # run locally
wrangler publish
```

## Deployment tips
- Configure secrets/env via your platform or `wrangler.toml`/cloud settings.
- Keep builds deterministic; no network is required during build.
- For CI, prefer `n3 build-target` with explicit flags.

## Exercises
1. Build a desktop bundle for an existing `.ai` file.
2. Create a Cloudflare worker build and inspect the generated `wrangler.toml`.
3. Run `n3 build mobile` and explore the generated config.
