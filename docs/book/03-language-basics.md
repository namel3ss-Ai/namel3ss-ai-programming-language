# Chapter 3 — Core Concepts

- **Apps & Pages:** An `app` declares an `entry_page`. Pages define routes and sections of UI.
- **Flows:** Ordered steps; each step has a `kind` (`ai`, `set`, `db_*`, `vector_*`, `tool`, `auth_*`, etc.).
- **AI Blocks:** Named models with `system` prompts, optional `memory` and `tools`.
- **Memory:** Short-term chat history, long-term summaries, profile facts, recall rules.
- **Data & RAG:** `frame` (table), `vector_store` (embeddings), `vector_index_frame`, `vector_query`.
- **Records & CRUD:** Typed records over frames plus `db_create/update/delete` and English `find <alias> where:` queries with ordering/pagination.
- **Tools:** HTTP JSON tools; invoke via `kind is "tool"` or AI tool-calling.
- **Auth:** Configure user model; use `auth_register/login/logout`; access `user.*`.
- **UI:** Sections with headings, text, inputs, buttons; `on click` performs flows or navigation.
- **Control Flow:** English `if / otherwise if / else`, `match / when / otherwise`, `guard` for preconditions, loops (`repeat for each`, `repeat up to N times`), `retry up to N times [with backoff]`, `on error`, and step kinds (`script`, `ai`, `agent`, `tool`). See `docs/language/control_flow.md` for the Control Flow v1 overview and the walkthrough in `docs/book/control_flow.md`.
- **Data & Collections:** Lists, records, frames, and collection pipelines (`keep/drop rows`, `group by`, `sort`, `take/skip`) plus safe record helpers and list utilities. See the walkthrough in `docs/book/data_and_collections.md` and the cheatsheet in `docs/language/data_collections.md`. For record queries, see `docs/book/records_and_queries.md`.

Cross-reference: parser for each construct in `src/namel3ss/parser.py`; runtime counterparts in `src/namel3ss/flows/engine.py`, `src/namel3ss/runtime/context.py`, `src/namel3ss/memory/*`, `src/namel3ss/tools/registry.py`, `src/namel3ss/runtime/auth.py`; tests across `tests/test_parser_*` and feature-specific files; examples: support_bot, rag_qa, tools_and_ai, crud_app.
