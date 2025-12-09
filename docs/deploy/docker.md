# Docker / Container usage

Build a development image:

```bash
docker build -t namel3ss:dev .
```

Run the CLI (override the default shell CMD):

```bash
docker run --rm -it \
  -e N3_OPENAI_API_KEY=sk-... \
  -e N3_MAX_PARALLEL_TASKS=8 \
  namel3ss:dev n3 --help
```

Run a server or flow runner (replace command as needed):

```bash
docker run --rm -it \
  -e N3_OPENAI_API_KEY=sk-... \
  -e N3_PROVIDER_CACHE_ENABLED=true \
  namel3ss:dev n3 run your_app.n3
```

The image runs as a non-root user by default. Provide secrets via environment variables or mounted files; no secrets are baked into the image.
