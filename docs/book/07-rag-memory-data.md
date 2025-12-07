# 7. RAG, Memory, and Data

## Memory
```ai
memory "support_history":
  type "conversation"
```
Use memory in agents/flows to keep context. Some advanced patterns may be experimental—check lint/diagnostics for guidance.

## Frames & data
Frames are persistent, table-like stores you can write and read from flows:

```ai
frame "conversations":
  backend "memory"   # or "sqlite" / "postgres" depending on your setup
  table "conversations"

flow "store_and_fetch":
  step "insert":
    kind "frame_insert"
    frame "conversations"
    values:
      user_id: state.user_id
      message: state.message

  step "load":
    kind "frame_query"
    frame "conversations"
    where:
      user_id: state.user_id

  let messages be step "load" output
  set state.messages be messages
```

`frame_insert` writes a row into the configured backend/table. `frame_query` returns a list of rows; if you omit `where`, it returns all rows. Filters use simple equality matching on the provided fields.

Updates and deletes round out CRUD:

```ai
step "update":
  kind "frame_update"
  frame "conversations"
  where:
    user_id: state.user_id
  set:
    name: state.new_name

step "delete":
  kind "frame_delete"
  frame "conversations"
  where:
    user_id: state.user_id
```

`frame_update` needs a `set` block; `frame_delete` requires `where` to avoid accidental full-table deletes. Update/delete return the number of affected rows as the step output.

## Event Log & Audit Trail
Namel3ss writes a structured audit trail into the `event_log` frame (created automatically if missing). Each run captures:

- flow start/end and status
- step start/end/error with names
- AI calls (model, status, latency/tokens where available)
- frame operations (insert/query/update/delete with row counts)

Query the log like any frame:

```ai
flow "recent_errors":
  step "load":
    kind "frame_query"
    frame "event_log"
    where:
      status: "error"

  let errors be step "load" output
  set state.errors be errors
```

Use this as the foundation for monitoring flows, dashboards, and Studio views.

## RAG basics
- Configure models and retrieval flows (`rewrite`, `lookup`, `compose`).
- Use frames or custom retrieval logic; keep examples lightweight to avoid heavy dependencies.

## Exercises
1. Define a conversation memory and reference it in an agent goal.
2. Create a frame over a CSV file and slice/filter it.
3. Sketch a three-step RAG flow: rewrite → lookup → answer.
