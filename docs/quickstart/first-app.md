# First App

1. Scaffold from the basic template:
   ```
   n3 init app-basic my-first-app
   cd my-first-app
   ```
2. Inspect `app.ai` to see an app, page, model, ai call, and flow.
3. Run the parser: `n3 parse app.ai`
4. Start the server: `n3 serve --dry-run` (or run FastAPI directly via `python -m namel3ss.server`).
5. Open Studio (see README) to view pages, flows, and diagnostics.

What happens:
- The default dummy model powers `ai "greet"` for deterministic output in dev/CI.
- The flow runs the ai call and can be invoked via `/api/run-flow` or the Studio Flows panel.
