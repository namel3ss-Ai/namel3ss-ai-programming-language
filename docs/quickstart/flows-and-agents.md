# Flows & Agents

Use the `examples/agents_and_flows/app.ai` program as a reference.

Key ideas:
- **Flows V3**: branching, parallel joins, error boundaries, shared state.
- **Agents V3**: planning, retries, reflection, team voting.

Try it:
```
n3 parse examples/agents_and_flows/app.ai
n3 run-flow --file examples/agents_and_flows/app.ai --flow orchestrate
```
This runs a flow that fans out work in parallel, calls an agent, and joins results back into shared state.

Studio: open the Flows & Automations panel to see flows and triggers; the Traces panel shows per-step spans.
