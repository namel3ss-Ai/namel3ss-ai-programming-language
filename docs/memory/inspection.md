# Memory inspection and context management

Namel3ss keeps conversational context lightweight by combining short‑term history, optional summarisation, and opt‑in vector recall. This page shows how to enable these features and how to inspect what actually goes to your models.

## Conversation summarisation

- Environment flags (disabled by default):
  - `N3_SUMMARY_ENABLED=true`
  - `N3_SUMMARY_MAX_MESSAGES` (default `50`)
  - `N3_SUMMARY_TARGET_LENGTH` (hint for summary size, default `1`)
- When enabled, older turns are summarised into a single `system` message before the model call; recent turns are preserved. If the summariser model fails, a simple fallback summary is used and the flow continues.
- Metrics: `conversation_summaries_total{status}` increments on success/failure.

## Vector memory recall (opt‑in)

- Environment flags (all optional, default disabled):
  - `N3_VECTOR_MEMORY_ENABLED=true`
  - `N3_VECTOR_MEMORY_STORE_NAME` (defaults to `default_vector`)
  - `N3_VECTOR_MEMORY_TOP_K` (defaults to `5`)
- When enabled and a vector store is configured, the runtime will:
  - Retrieve relevant chunks for the current user input and inject them as a `system` context message.
  - Upsert the latest user/assistant turns back into the vector store for long‑term recall.

### Example pattern

```
export N3_SUMMARY_ENABLED=true
export N3_SUMMARY_MAX_MESSAGES=40
export N3_VECTOR_MEMORY_ENABLED=true
export N3_VECTOR_MEMORY_STORE_NAME=kb
export N3_VECTOR_MEMORY_TOP_K=3
```

Run your flow as usual (e.g., `n3 run-flow --file app.ai --flow support_chat`). The model will see a summarised history plus the top‑K vector matches as additional context.

## Inspecting memory and context

Use the CLI to view the context last sent to a model (per session/AI):

```
n3 memory-inspect --session-id sess-123 --ai-id support_agent
```

The command prints a JSON snapshot containing the recall messages (including any summaries) and, if available, conversation data stored by the memory engine. Snapshots are kept in‑process and are best used during development and tests.

You can also call the helper programmatically:

```python
from namel3ss.memory.inspection import inspect_memory_state

snapshot = inspect_memory_state("sess-123", ai_id="support_agent")
```

If vector memory is enabled but misconfigured, the runtime raises a `ProviderConfigError` with a clear message so you can fix the store name or credentials.
