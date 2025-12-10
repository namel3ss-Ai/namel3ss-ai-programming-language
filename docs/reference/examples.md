# Examples

Built-in examples live under `examples/<name>/<name>.ai` and are intended to stay runnable and easy to inspect.

## Listing examples
```bash
n3 example list
```

## Running an example
```bash
n3 example run hello_world
```

On success the CLI prints JSON status and, when available, a Studio link:
```
Open in Studio (trace):
http://localhost:8000/studio?trace=trace_12345
```

## Loading example source in Studio
Open Studio with an `example` query param:
```
http://localhost:8000/studio?example=multi_agent_debate
```
The IDE will fetch `/api/example-source?name=multi_agent_debate`, load the source into the workspace, and focus the IDE panel.

You can also load the new flagship examples:
- `rag_qa` — RAG-powered Q&A over a small built-in knowledge base.
  - CLI: `n3 example run rag_qa`
  - Studio source: `http://localhost:8000/studio?example=rag_qa`
- `support_bot` — Support assistant using agents, flows, a logging tool step, and conversation memory.
  - CLI: `n3 example run support_bot`
  - Studio source: `http://localhost:8000/studio?example=support_bot`
- `control_flow_demo` — Control Flow v1 walkthrough showing guard, match, loops, retry, and on error together.
  - CLI: `n3 example run control_flow_demo`
  - Studio source: `http://localhost:8000/studio?example=control_flow_demo`
- `data_collections_demo` — Pipelines, grouping with aggregates, safe record access, and list helpers in one flow.
  - CLI: `n3 example run data_collections_demo`
  - Studio source: `http://localhost:8000/studio?example=data_collections_demo`
- `records_queries_demo` — English record queries with `find`, ordering, and pagination over sample data.
  - CLI: `n3 example run records_queries_demo`
  - Studio source: `http://localhost:8000/studio?example=records_queries_demo`

- `records_validation_demo` - Field validation showcase with numeric bounds, enum membership, array limits, and transaction rollbacks.
  - CLI: `n3 example run records_validation_demo`
  - Studio source: `http://localhost:8000/studio?example=records_validation_demo`
- `memory_profiles_demo` - Memory profiles and inline overrides for conversational assistants.
  - CLI: `n3 example run memory_profiles_demo`
  - Studio source: `http://localhost:8000/studio?example=memory_profiles_demo`

## Inspecting traces in Studio
If you have a trace id (from the CLI output), open:
```
http://localhost:8000/studio?trace=<trace_id>
```
Studio will fetch that trace and open a trace detail view.
