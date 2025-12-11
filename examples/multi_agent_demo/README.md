# Multi-agent orchestration demo

This example sketches a simple router + specialist setup:

- A `router` agent with a `role` of router and `can_delegate_to` set to two workers.
- Two specialist agents (`billing_agent`, `tech_agent`) that would handle routed work.
- A tiny flow `support_entry` that calls the router; in a fuller app you would branch on `state.last_output` to invoke the chosen worker.

The goal is to show the DSL surface for multi-agent patterns without forcing a full runtime dependency.
