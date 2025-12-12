# Chapter 14 — Studio: Building, Debugging & Inspecting

- **UI Preview:** Renders pages/sections/components; inputs bind to `state.*`.
- **Flow execution:** Buttons fire `/api/ui/flow/execute`; see results in the console.
- **Memory Inspector:** Shows short/long/profile state and recall snapshots per AI/session.
- **Provider Status:** Surfaces configured providers and key presence.

## Binding flow output to page state

UI click handlers can pipe a flow’s return value straight into page state:

```
flow is "support_flow":
  step is "answer":
    return "Hello!"

page is "chat" at "/":
  state answer is ""
  button "Ask":
    on click:
      do flow "support_flow" output to state.answer
  text state.answer
```

Clicking **Ask** runs the flow and updates `state.answer`, so the page re-renders immediately.

## Launching Studio

- Packaged build: `n3 studio`
- Dev mode (daemon + watcher): `n3 studio dev`
- Defaults: backend `8000` (`--backend-port`). The `--port/--ui-port` flag is kept for compatibility but ignored.
- Studio is served at `/studio` (local); `/studio-static` temporarily redirects for compatibility.
- Auto-discovers your project; override with `--project <path>`. Use `--no-open` to skip launching the browser.
- If no `.ai` files are found in an interactive shell, you?ll be offered a starter app to get going.

## System Map (Canvas)
- Read-only map of your program derived from IR (apps, pages, flows, AI, agents, tools, memory, RAG, evaluations).
- Open the **Canvas** panel in Studio to see nodes grouped by type; click a node to view details.
- Always IR-backed—no Studio-only state—and safe to view even when the program has errors.

## Inspectors
- Click any Canvas node (or choose from the Inspector dropdown) to see a structured, read-only view of pages, flows, AI, agents, tools, memory, and evaluations.
- Shows routes, models, tools, memory bindings, and linked entities directly from IR—no extra Studio state.

## Flow Execution Viewer
- Open the **Run** tab and use the Flow Execution Viewer to run any flow from the current project (no code paste required).
- Select a flow, optionally provide JSON for `state`/`metadata`, and view a narrative timeline of each step (kind, target, duration, errors).
- AI steps link to the AI Call Visualizer; memory-aware steps jump to the Memory Viewer; errors surface ask links to Ask Studio.
- Recent runs are kept in-session so you can replay or revisit the last few timelines quickly.
- When you click a flow in the Canvas or Inspector, it pre-selects that flow in the runner so you can execute it immediately.

## Presentation Mode
- Toggle the **Presentation** button in the header (or press Shift+P) to hide chrome and focus on the content.
- Works across Canvas, Flow timelines, RAG visualizer, AI Call, Memory, and Inspectors—ready for screenshots or demos.
- Light/dark aware; toggle off to return to the full tool chrome.

## Re-Parse Now
- If file watchers miss changes or you want an immediate rebuild, use **Re-Parse Now** (header button and in Canvas/Inspector).
- Forces the daemon to rebuild IR immediately and refreshes Status, Canvas, Inspector, Flow Runner, Memory, and RAG views.
- On errors, you’ll see a banner with details and can jump to Ask Studio for guidance.

## Best Practices & Warnings
- Studio runs a light best-practices pass on the IR and surfaces non-fatal warnings (flow/tool/AI/RAG/memory).
- See the warning badge in the header; open it to view grouped warnings with entity, file, and code.
- Inspectors show per-entity warning hints; click through to jump to the right panel or ask Ask Studio to explain/fix.
- Examples: flows without error handling, HTTP tools without auth, tools missing timeouts, RAG pipelines without rerank/answer stages, unused memories.

## Memory & Context Viewer
- Open the **Memory & Context** tab to see which AIs have memory configured and how they’re scoped.
- Inspect the memory plan (short_term/long_term/profile/episodic/semantic, scopes, retention, PII, recall rules).
- Browse sessions for a selected AI and view context: conversation history, stored items, and recall snapshots/diagnostics.
- From Flow Runner or AI Inspector you can jump straight into this panel with the AI pre-selected (and session when available).

## AI Call Visualizer
- Open the **AI Call** tab to see exactly what the model saw for a given AI call.
- Shows system prompt, user input, recalled memory (short/long/profile/episodic/semantic), vector/RAG context, and recall diagnostics.
- Jump in from Flow Runner (AI steps), the Memory panel (session view), or any place where AI + session is known.

## Ask Studio
- Ask natural-language questions inside Studio; it uses your configured provider via ModelRegistry.
- Explains IR errors, flow failures, tool issues, and suggests DSL snippets—read-only advice (no automatic edits).
- Trigger from the Ask Studio tab or contextual links (IR error banner, Flow Runner errors, memory/AI inspectors).

### Generating DSL with Ask Studio
- Choose a mode in the Ask panel (Explain, Flow, Page, Tool, Agent, RAG).
- Ask Studio returns structured, copy-ready Namel3ss snippets (English-first headers; no braces).
- Snippet cards show kind + notes and include a Copy button; you apply them manually (read-only).
- Contextual links (e.g., “Ask Studio” from flow errors) can pre-select generation modes automatically.

Workflow:
1) Open your `.ai` in Studio.  
2) Edit UI/flows and watch the preview refresh.  
3) Click buttons to execute flows; inspect step outputs and errors.  
4) Open Memory Inspector to see what context was recalled.  
5) Check provider status if AI calls fail due to config.

Cross-reference: backend endpoints in `src/namel3ss/server.py` (UI manifest, flow execute, memory inspector, provider status); UI runtime `src/namel3ss/ui/manifest.py`, `src/namel3ss/ui/runtime.py`; tests `tests/test_studio_http.py`, `tests/test_memory_inspector_api.py`, `tests/test_ui_flow_execute.py`; examples: run `examples/support_bot/support_bot.ai` or `examples/rag_qa/rag_qa.ai` in Studio.
