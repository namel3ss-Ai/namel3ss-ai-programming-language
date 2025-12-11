# Macro Plans Demo

This example shows how the structured macro plan engine can compose multiple stdlib macros:

- `crud_ui` builds a basic CRUD experience for an `Order` record.
- `auth_ui` adds a lightweight login/logout scaffold.
- `analytics_dashboard` adds a simple dashboard + retrieval/agent context for metrics.

Run `n3 macro expand examples/macro_plans_demo/app.ai` to see the generated DSL.
