# Chapter 14 — Studio: Building, Debugging & Inspecting

- **UI Preview:** Renders pages/sections/components; inputs bind to `state.*`.
- **Flow execution:** Buttons fire `/api/ui/flow/execute`; see results in the console.
- **Memory Inspector:** Shows short/long/profile state and recall snapshots per AI/session.
- **Provider Status:** Surfaces configured providers and key presence.

Workflow:
1) Open your `.ai` in Studio.  
2) Edit UI/flows and watch the preview refresh.  
3) Click buttons to execute flows; inspect step outputs and errors.  
4) Open Memory Inspector to see what context was recalled.  
5) Check provider status if AI calls fail due to config.

Cross-reference: backend endpoints in `src/namel3ss/server.py` (UI manifest, flow execute, memory inspector, provider status); UI runtime `src/namel3ss/ui/manifest.py`, `src/namel3ss/ui/runtime.py`; tests `tests/test_studio_http.py`, `tests/test_memory_inspector_api.py`, `tests/test_ui_flow_execute.py`; examples: run `examples/support_bot/support_bot.ai` or `examples/rag_qa/rag_qa.ai` in Studio.
