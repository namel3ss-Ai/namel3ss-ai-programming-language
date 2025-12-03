# Agents & Flows Example

Demonstrates parallel/branching flow logic and an agent.

Commands:
```
n3 parse examples/agents_and_flows/app.ai
n3 run-flow --file examples/agents_and_flows/app.ai --flow orchestrate
```

The flow calls an ai "decide" step, then runs an agent, and joins the result. Traces/metrics are viewable in Studio.
