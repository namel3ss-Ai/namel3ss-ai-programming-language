# Support Bot Example

A lightweight support assistant that classifies incoming issues, responds via an agent, and logs interactions through a tool step while keeping a conversation history.

## Run with the CLI
```bash
n3 run support_flow --file examples/support_bot/support_bot.ai
```

## Load in Studio
Open the IDE with:
```
http://localhost:8000/studio
```

When you run via the CLI, you’ll see a trace link like:
```
Open in Studio (trace):
http://localhost:8000/studio?trace=<trace_id>
```
Use it to inspect agent reasoning, tool calls, and memory interactions.
