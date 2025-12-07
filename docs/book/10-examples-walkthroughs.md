# 10. Example Walkthroughs

## Hello World
Path: `examples/hello_world/hello_world.ai`
Run:
```bash
n3 run hello-world --file examples/hello_world/hello_world.ai
```
Shows a simple page with heading/text using modern syntax.

## Support Bot (flows + agents + memory)
Path: `examples/support_bot/support_bot.ai`
Run:
```bash
n3 run support_flow --file examples/support_bot/support_bot.ai
```
Inspect traces in Studio to see AI classification, agent response, and logging.

## Expressions & Data Pipelines
Path: `examples/expressions.ai` and `examples/gallery/data_processing.ai`
Demonstrates expressions, list built-ins, helpers, and logging.

## RAG and Frames (lightweight)
Path: `examples/rag_qa/rag_qa.ai`
Uses a simple retrieval flow skeleton. Treat as a template; configure your own data/models.
Note: RAG/memory features beyond this skeleton may be experimental; check diagnostics/lint for guidance.

## UI patterns
Paths under `examples/ui/` and `examples/getting_started/app.ai`
Show forms, layout, styling, and components with the modern page syntax.

## Exercises
1. Clone an example into a new file and rename the app/page.
2. Add a button to an existing page that calls a flow.
3. Add logging to a flow step and view it in Studio traces.
