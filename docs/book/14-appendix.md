# Chapter 16 — Appendix: Syntax Reference (from the Parser)

- **App:** `app is "name":` then `entry_page is "page"`.
- **Page:** `page is "name" at "/route": ...` with sections/components; navigation allowed in `on click`.
- **Sections & UI:** `section is "name":` with `heading`, `text`, `image`, `input`, `textarea`, `button`, layout (rows/columns/cards/badges/chat where supported), optional `when/show`, `class/style`.
- **Models:** `model is "name": provider is "..."`.
- **AI:** `ai is "name": model is "..."; system is "..."; input from <expr>; tools: ["tool_a"]; memory: ...; streaming flags on steps.`
- **Memory:** Declare `memory is "name": type is "conversation"`; in AI `memory: kinds: short_term/long_term/profile` with `window`, `store`, `scope`, `retention_days`, `pii_policy`, `pipeline`; `recall` list.
- **Flows:** `flow is "name": step is "s": kind is "..."; when <expr>; for each <var> in <expr>: ...; on error: ...; let <local> be ...; set state.<field> be ...; read step.<name>.output`.
- **Data & RAG:** `frame is "name": backend/table`; `vector_store is "name": frame is "..."; text_column/id_column/embedding_model`; steps `vector_index_frame`, `vector_query`.
- **Records & CRUD:** `record is "Name": frame is "..."; fields: <field>: type/primary_key/required/default`; steps `db_create`, `db_get`, `db_update`, `db_delete` with `values`, `where`, `by id`, `set`.
- **Tools:** `tool is "name": kind is "http_json"; method/url/query/headers/body`; flow step `kind is "tool"` with `input`; AI `tools` list for tool-calling.
- **Auth:** `auth:` with `user_record`, `id_field`, `identifier_field`, `password_hash_field`; steps `auth_register/login/logout`; expressions under `user.*`.
- **Providers:** per-model/AI `provider`; config via `namel3ss.config.*`; errors `N3L-1800`, `N3P-1801`, `N3P-1802`.
- **Diagnostics:** variable scope/unknown references/invalid UI placement handled in parser/diagnostics; see `tests/test_variable_scope.py`, `tests/test_ui_button_navigate_validate.py`.

Authoritative grammar: `src/namel3ss/parser.py`. Semantics: runtime modules cited per chapter. Behavioural expectations: tests under `tests/`. End-to-end references: `examples/`.
