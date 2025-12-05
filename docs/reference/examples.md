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

## Inspecting traces in Studio
If you have a trace id (from the CLI output), open:
```
http://localhost:8000/studio?trace=<trace_id>
```
Studio will fetch that trace and open a trace detail view.
