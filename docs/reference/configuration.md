# Configuration & API Keys

Namel3ss reads configuration from environment variables (and optional project config if you add one). Keep everything in one place so you always know which model and backend are in use.

## AI providers

Configure providers generically (examples):

```yaml
providers:
  openai:
    type: openai
    api_key_env: OPENAI_API_KEY
    base_url: https://api.openai.com/v1
  anthropic:
    type: anthropic
    api_key_env: ANTHROPIC_API_KEY
    base_url: https://api.anthropic.com
  local_ollama:
    type: http_json
    base_url: http://localhost:11434
    path: /api/chat
    headers:
      Content-Type: application/json
  azure_openai:
    type: azure_openai
    api_key_env: AZURE_OPENAI_API_KEY
    base_url: https://my-resource.openai.azure.com
    deployment: my-gpt4o-deployment
    api_version: 2024-06-01
  gemini:
    type: gemini
    api_key_env: GEMINI_API_KEY
    base_url: https://generativelanguage.googleapis.com
    api_version: v1beta
```

Set API keys in env:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-..."
export GEMINI_API_KEY="sk-..."
```

Optional base URLs:

```bash
export N3_OPENAI_BASE_URL="https://api.openai.com/v1"
export N3_ANTHROPIC_BASE_URL="https://api.anthropic.com"
export N3_GEMINI_BASE_URL="https://generativelanguage.googleapis.com"
```

Local/custom HTTP providers (`type: http_json`) accept any reachable HTTP endpoint. The runtime sends:

```json
{
  "model": "<remote_name>",
  "messages": [{ "role": "system", "content": "..." }, ...]
}
```

and expects a response containing `content` (or a nested path you configure).

## Default models

Choose defaults when your DSL does not specify one:

```bash
export N3_DEFAULT_CHAT_MODEL="openai:gpt-4.1-mini"
export N3_DEFAULT_EMBEDDING_MODEL="text-embedding-3-large"
```

Map logical models to providers:

```yaml
models:
  gpt-4.1-mini:
    provider: openai
    remote_name: gpt-4.1-mini
    kind: chat
  claude-3-opus:
    provider: anthropic
    remote_name: claude-3-opus-20240229
    kind: chat
  azure-gpt4o:
    provider: azure_openai
    remote_name: my-gpt4o-deployment
    kind: chat
  local-llama-chat:
    provider: local_ollama
    remote_name: llama3.1:latest
    kind: chat
  gemini-1.5-pro:
    provider: gemini
    remote_name: gemini-1.5-pro
    kind: chat
  gemini-embedding:
    provider: gemini
    remote_name: text-embedding-004
    kind: embedding
```

## Embeddings

Embeddings use the same OpenAI key by default, but you can override:

```bash
export N3_EMBEDDINGS_PROVIDER="openai"
export N3_EMBEDDINGS_MODEL="text-embedding-3-small"
export N3_EMBEDDINGS_BASE_URL="https://api.openai.com/v1"
```

## Database / frames

Frames and the event log can use a database URL:

```bash
export DATABASE_URL="sqlite:///local.db"  # or postgres://...
```

If unset, in-memory storage is used for frames and logging.

## Troubleshooting

- **Missing key**: errors will mention the exact env var (e.g., `N3_OPENAI_API_KEY` or `OPENAI_API_KEY`).
- **Unknown model**: configure `N3_DEFAULT_CHAT_MODEL` or set a model in your DSL.
- **No DB URL**: set `DATABASE_URL` if you need persistence beyond process memory.
