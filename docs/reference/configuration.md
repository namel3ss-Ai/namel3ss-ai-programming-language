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

## Memory stores

Conversation memory persists through named stores declared in project/server config (or via `N3_MEMORY_STORES_JSON`). Each entry supplies a `kind` plus backend-specific fields:

```toml
[memory_stores.default_memory]
kind = "in_memory"

[memory_stores.chat_long]
kind = "sqlite"
url = "sqlite:///var/namel3ss/chat-long.db"
```

Supported kinds today:

- `in_memory` – process-local dictionary (default, great for tests/dev).
- `sqlite` – file-backed conversation log. Requires `url` or `path`; use `sqlite:///relative/or/absolute.db`.

Set the map directly through env when running outside a project config:

```bash
export N3_MEMORY_STORES_JSON='{
  "default_memory": {"kind": "in_memory"},
  "chat_long": {"kind": "sqlite", "url": "sqlite:///memory.db"}
}'
```

If you omit the `memory_stores` block entirely, Namel3ss injects `default_memory` automatically so AIs with `memory` continue to work out of the box. Referencing an undeclared store triggers diagnostic `N3L-1201` during compilation (and again at runtime if validation was skipped). Misconfigured or unsupported stores raise `N3L-1204` at startup.

Multi-kind memories wire up each store independently:

```
memory:
  kinds:
    short_term:
      window is 12         # defaults to 20
    long_term:
      store is "chat_long"
    profile:
      store is "user_profile"
      extract_facts is true
  recall:
    - source is "short_term"
      count is 8
    - source is "long_term"
      top_k is 4
    - source is "profile"
      include is true
```

- `short_term` keeps the rolling chat buffer (usually backed by `default_memory`).
- `long_term` and `profile` point to additional stores (sqlite, Redis, vector DB, etc.).
- `recall` dictates how many entries from each source get prepended to the provider call.
- Legacy `memory: kind is "conversation"` is normalized to a `short_term` section with a default recall rule so existing DSL compiles unchanged.
- Privacy controls:
  - `retention_days` trims historical entries older than the specified number of days.
  - `pii_policy` (`"none"` or `"strip-email-ip"`) scrubs sensitive strings before writing to long-lived stores.
  - `scope` controls how entries are keyed: `"per_session"` (default for short-term), `"per_user"` (default for long-term/profile when a user id exists), or `"shared"`. If a per-user scope is requested but no user id is available, Namel3ss falls back to per-session and surfaces that fallback in Studio.

### Memory Pipelines

Long-term and profile kinds can include a `pipeline:` list describing post-processing steps:

```
memory:
  kinds:
    long_term:
      store is "chat_long"
      pipeline:
        - step is "summarize_session"
          type is "llm_summarizer"
          max_tokens is 512
    profile:
      store is "user_profile"
      pipeline:
        - step is "extract_facts"
          type is "llm_fact_extractor"
```

- `step` is a friendly label for logs/diagnostics; `type` selects the built-in pipeline.
- Supported types today:
  - `llm_summarizer`: summarizes the recent short-term transcript + latest exchange and appends a concise note to the long-term store. `max_tokens` is optional.
  - `llm_fact_extractor`: extracts durable bullet-point facts about the user from the conversation and appends them to the profile store.
- Pipelines run immediately after each AI call using the configured provider/model. Unknown `type` values raise `N3L-1203`. The stored summaries/facts are then available to the recall plan on subsequent turns.

## Troubleshooting

- **Missing key**: errors will mention the exact env var (e.g., `N3_OPENAI_API_KEY` or `OPENAI_API_KEY`).
- **Unknown model**: configure `N3_DEFAULT_CHAT_MODEL` or set a model in your DSL.
- **No DB URL**: set `DATABASE_URL` if you need persistence beyond process memory.
