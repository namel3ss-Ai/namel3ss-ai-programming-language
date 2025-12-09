# Chapter 3 — Core Concepts

- **Apps & Pages:** An `app` declares an `entry_page`. Pages define routes and sections of UI.
- **Flows:** Ordered steps; each step has a `kind` (`ai`, `set`, `db_*`, `vector_*`, `tool`, `auth_*`, etc.).
- **AI Blocks:** Named models with `system` prompts, optional `memory` and `tools`.
- **Memory:** Short-term chat history, long-term summaries, profile facts, recall rules.
- **Data & RAG:** `frame` (table), `vector_store` (embeddings), `vector_index_frame`, `vector_query`.
- **Records & CRUD:** Typed records over frames plus `db_create/get/update/delete`.
- **Tools:** HTTP JSON tools; invoke via `kind is "tool"` or AI tool-calling.
- **Auth:** Configure user model; use `auth_register/login/logout`; access `user.*`.
- **UI:** Sections with headings, text, inputs, buttons; `on click` performs flows or navigation.

Cross-reference: parser for each construct in `src/namel3ss/parser.py`; runtime counterparts in `src/namel3ss/flows/engine.py`, `src/namel3ss/runtime/context.py`, `src/namel3ss/memory/*`, `src/namel3ss/tools/registry.py`, `src/namel3ss/runtime/auth.py`; tests across `tests/test_parser_*` and feature-specific files; examples: support_bot, rag_qa, tools_and_ai, crud_app.
