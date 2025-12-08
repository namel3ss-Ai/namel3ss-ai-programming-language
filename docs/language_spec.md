# Namel3ss Language Specification (V3)

This document describes the Namel3ss V3 language as it exists today. It mirrors the current lexer/parser/IR and the validation rules enforced at runtime. No grammar changes are introduced here; all constraints are enforced via validation and diagnostics.

The English-style surface is now frozen for the 1.0 line: legacy symbolic forms stay supported for backwards compatibility, but the preferred style is documented in `docs/language/style_guide.md` and enforced via the lint rules in `docs/language/lint_rules.md`.

## Top-Level Declarations

Supported block kinds:
- `app`
- `page`
- `model`
- `ai`
- `agent`
- `flow`
- `memory`
- `frame`
- `macro`
- UI pages with layout (Phase UI-1)
- `plugin`
- UI blocks: `section`, `component`

Rules:
- Identifiers are case-sensitive strings; names must be unique per block kind (e.g., you cannot define two `page` blocks with the same name).
- Files may contain multiple blocks of different kinds. The IR enforces uniqueness during compilation.
- An `app` declares an `entry_page` that must reference an existing `page`.

## Block Contracts

Each block kind has required and optional fields aligned with the current IR:

- **app**
  - required: `name`, `entry_page`
  - optional: `description`
  - relationships: `entry_page` must reference a `page`.

- **page**
  - required: `name`, `route`
  - optional: `title`, `description`, `properties`
  - children: `section` blocks; sections contain `component` blocks.
  - references: may list `ai` calls, `agent`s, and `memory` spaces by name.

- **model**
  - required: `name`, `provider`
  - optional: —

- **ai**
  - required: `name`, `model_name`, `input_source`
  - optional: `system "<string>"` (exactly one; prepended as a system-role message)
  - references: `model_name` must reference a declared `model`.

- **agent**
  - required: `name`
  - optional: `goal`, `personality`, `system "<string>"` (exactly one)

- **flow**
  - required: `name`
  - optional: `description`
  - children: ordered `step`s with `kind` in `{ai, agent, tool}` and a `target`.
  - statements: `let/set` inside script steps for local variables and state updates.
  - references: `ai`/`agent` targets must exist; tool targets must be registered/builtin.
- **Streaming metadata (AI steps)**
  - Example:
    ```
    step is "answer":
      kind is "ai"
      target is "support_bot"
      streaming is true
      stream_channel is "chat"
      stream_role is "assistant"
      stream_label is "Support Bot"
      stream_mode is "tokens"
    ```
  - Fields:
    - `streaming` enables streaming for the AI step.
    - `stream_channel` hints where to surface the stream (`chat`, `preview`, `logs`, etc.).
    - `stream_role` / `stream_label` describe the speaker (assistant/system/tool).
    - `stream_mode` controls granularity: `tokens` (default), `sentences`, `full`.
  - These properties are part of the language/IR and flow into runtime StreamEvent objects; the HTTP/SSE API is just one transport.

- **memory**
  - required: `name`, `memory_type` (one of `conversation`, `user`, `global`)

- **frame**
  - required: `name`, `from file "<path>"`
  - optional: `with delimiter ","`, `has headers`, `select col1, col2`, `where <expression>`
  - semantics: loads CSV/tabular data lazily, applies optional `where` filters and `select` projections, and behaves like a list of record rows in expressions, filters/maps, aggregates, and loops.
- **macro**
  - required: `name`, `using ai "<model>"`, `description`
  - optional: `sample`, `parameters`
  - semantics: defines an AI-assisted macro that expands to Namel3ss code when invoked with `use macro "name"` (optionally with arguments). Expansions are parsed, linted, and merged at load-time.
- **page (UI layout)**
  - required: `name`, `at "<route>"` starting with `/`, layout block
  - layout: `section`, `heading`, `text`, `image`, `use form "<name>"`, UI-2 controls (`state`, `input`, `button`, `when/otherwise` with `show:`)
  - semantics: declares a UI page layout; UI-2 adds reactive state, inputs, buttons with `on click`, and conditional visibility.

- **plugin**
  - required: `name`
  - optional: `description`

- **section**
  - required: `name`
  - children: `component`

- **component**
  - required: `type`
  - optional: `props` (key/value dictionary)

## Naming & Uniqueness
- Names must be unique per block kind (apps, pages, models, ai, agents, flows, memories, plugins).
- Section names must be unique within a page; component ordering is preserved.

## Expressions & Values
- Variables: `let <name> be <expression>` (or `let <name> = <expression>`) declares a variable in the current flow/agent scope. Redeclaring in the same scope is an error.
- Mutation: `set <name> to <expression>` updates an existing variable. Assigning to an undefined variable is an error.
- Frames: frame values behave like lists of record rows and can be iterated (`repeat for each row in sales_data`), filtered/mapped (`all row from sales_data where ...`), and aggregated (`sum of all row.revenue from sales_data`).
- Macros: `use macro "name"` expands AI-generated code at load-time; macro definitions capture description/sample/parameters.
- Built-in AI macro `crud_ui` generates CRUD flows, forms, and UI pages for an entity:
  - `use macro "crud_ui" with: entity "Product" fields ["name", "price"]`
- UI pages: `page "name" at "/route":` with layout elements for static rendering; sections group layout children; `use form` embeds previously declared forms. UI-2 adds `state`, `input "label" as var [type is ...]`, `button "Label": on click: ...`, and conditional blocks `when <expr>: show: ... otherwise: ...`.
- Literals: strings, booleans (`true`/`false`), and numbers (int/float).
- Operators:
  - Logical: `and`, `or`, `not`
  - Comparisons: `==`, `!=`, `<`, `>`, `<=`, `>=` plus English forms (`is greater than`, `is less than`, `is at least`, `is at most`)
  - Arithmetic: `+`, `-`, `*`, `/`, `%` plus English forms (`plus`, `minus`, `times`, `divided by`)
- Precedence (lowest to highest): `or`, `and`, `not`, comparisons, `+/-`, `*//%`, unary `+/-`, primary (identifiers, literals, parentheses).
- Conditions must evaluate to booleans; type mismatches, divide-by-zero, and invalid operators surface diagnostics.
- String built-ins:
  - English: `trim of expr`, `lowercase of expr`, `uppercase of expr`, `replace <old> with <new> in <text>`, `split <text> by <sep>`, `join <list> with <sep>`, `slugify of expr`
  - Functional: `trim(expr)`, `lowercase(expr)`, `uppercase(expr)`, `replace(text, old, new)`, `split(text, sep)`, `join(list, sep)`, `slugify(expr)`
  - Diagnostics: `N3-4000` string type mismatch, `N3-4001` join requires list of strings, `N3-4002` split separator must be string, `N3-4003` replace args must be strings.
- Numeric built-ins:
  - English: `minimum of list`, `maximum of list`, `mean of list`, `round value to precision`, `absolute value of expr`
  - Functional: `min(list)`, `max(list)`, `mean(list)`, `round(value, precision)`, `abs(expr)`
  - Diagnostics: `N3-4100` aggregates require non-empty numeric list, `N3-4101` invalid precision for round, `N3-4102` invalid numeric type.
- Boolean helpers:
  - English: `any var in list where predicate`, `all var in list where predicate`
  - Functional: `any(list, where: predicate)`, `all(list, where: predicate)`
  - Diagnostics: `N3-4200` any/all requires list, `N3-4201` predicate must be boolean.
- Time/random helpers: `current timestamp`, `current date`, `random uuid` and their functional forms. Passing arguments raises `N3-4300`.

## AI Conversation Memory & Stores

AI blocks can now compose multiple memory kinds and declare how each one is recalled:

```
ai is "support_bot":
  model is "gpt-4.1-mini"
  system is "You are a helpful support assistant."
  memory:
    kinds:
      short_term:
        window is 12
      long_term:
        store is "chat_long"
      profile:
        store is "user_profile"
        extract_facts is true
    recall:
      - source is "short_term"
        count is 10
      - source is "long_term"
        top_k is 5
      - source is "profile"
        include is true
```

- `short_term` keeps the rolling conversation buffer (`window` defaults to 20 messages, stored in `default_memory` unless overridden).
- `long_term` points at a configured memory store (e.g., sqlite-backed log or vector DB). The runtime retrieves the last/top-k items and prepends them to the model context.
- `profile` holds durable user facts. When `extract_facts` is true, the runtime appends the user's latest message to this store (future phases will extract structured facts).
- `recall` defines how these sources are merged into the prompt. `source` must match one of the declared kinds; additional settings (`count`, `top_k`, `include`) control how much context is pulled in. Referencing a source without a matching kind raises `N3L-1202`.

Memory stores are configured project-wide:

```
[memory_stores.default_memory]
kind = "in_memory"

[memory_stores.chat_long]
kind = "sqlite"
url = "sqlite:///memory.db"

[memory_stores.user_profile]
kind = "sqlite"
url = "sqlite:///profiles.db"
```

If no stores are configured, Namel3ss injects an in-memory `default_memory` for development. Unsupported store kinds or missing backend fields (e.g., omitting `url` for a `sqlite` store) raise `N3L-1204` during startup.

Legacy form:

```
memory:
  kind is "conversation"
  window is 20
  store is "chat_long"
```

is automatically normalized to `short_term` + a default recall rule, so existing apps keep working.

### Memory Pipelines

Long-term and profile memories can also define post-processing pipelines that run after every AI turn:

```
ai is "support_bot":
  model is "gpt-4.1-mini"
  memory:
    kinds:
      long_term:
        store is "chat_long"
        pipeline:
          - step is "summarize_session"
            type is "llm_summarizer"
            max_tokens is 512
      profile:
        store is "user_profile"
        pipeline:
          - step is "extract_facts"
            type is "llm_fact_extractor"
    recall:
      - source is "short_term"
        count is 10
      - source is "long_term"
        top_k is 5
      - source is "profile"
        include is true
```

- `llm_summarizer` compresses the recent conversation (short-term history plus the latest exchange) and appends summaries into the long-term store.
- `llm_fact_extractor` pulls durable user facts from the interaction and appends them to the profile store.
- Pipelines run in the order declared; each entry must provide `step` (a friendly name) and `type`. Unknown pipeline types raise `N3L-1203`. `max_tokens` is optional and only applies to `llm_summarizer`.
- The resulting summaries/facts are available to recall rules (e.g., `long_term` `top_k` or `profile` `include`) on subsequent turns, completing the short/long/profile memory loop.
- Canonical DSL: The English-style surface is the primary, modern syntax. Legacy symbolic/colon forms remain supported via automatic transformation, but lint will suggest migrating to the English forms. All examples in this spec use the modern syntax.

### Memory Privacy, Retention & Scope

Each memory kind can now declare retention, PII policies, and scope, giving you fine-grained control over how long data lives, how it is scrubbed, and who shares it:

`
ai is "support_bot":
  model is "gpt-4.1-mini"
  memory:
    kinds:
      short_term:
        window is 20
        retention_days is 7
        scope is "per_session"
      long_term:
        store is "chat_long"
        retention_days is 365
        pii_policy is "strip-email-ip"
        scope is "per_user"
      profile:
        store is "user_profile"
        retention_days is 365
        pii_policy is "strip-email-ip"
        scope is "per_user"
    recall:
      - source is "short_term"
        count is 12
      - source is "long_term"
        top_k is 5
      - source is "profile"
        include is true
`

- 
etention_days: maximum age of entries for that kind. Anything older is filtered out automatically and periodically cleaned from the backend.
- pii_policy: "
one" (default) or "strip-email-ip". When set, stored summaries/facts have emails/IP addresses replaced with placeholders.
- scope: "per_session", "per_user", or "shared". Short-term defaults to per-session; long-term/profile default to per-user when a user id is present, otherwise per-session. If a per-user scope is requested but no user id is available, the runtime falls back to per-session and surfaces a diagnostic note in Studio.

Studio's Memory Inspector shows these policies (scope, retention, PII handling, and any fallbacks) for each kind so you can verify how data is governed at runtime.

- Pattern matching:
  - `match <expr>:` with `when <pattern>:` branches and optional `otherwise:`.
  - Patterns may be literals, comparisons, or success/error bindings (`when success as value:` / `when error as err:`).
  - Diagnostics: `N3-4300` invalid pattern, `N3-4301` missing match value, `N3-4302` incompatible pattern type, `N3-4400` misuse of success/error patterns.
- Retry:
  - `retry up to <expr> times:` with optional `with backoff`.
  - Count must be numeric and at least 1 (`N3-4500` / `N3-4501`).
- Collections:
- List literals `[a, b, c]`, indexing `xs[0]`, slicing `xs[1:3]`, prefix/suffix slices `xs[:2]` / `xs[2:]`. Negative indices are supported (Python-style): `xs[-1]`, `xs[-3:-1]`, `xs[:-2]`. Out-of-bounds indexing raises `N3-3205`.
  - List built-ins available in English (`length of xs`, `first of xs`, `last of xs`, `sorted form of xs`, `reverse of xs`, `unique elements of xs`, `sum of xs`) and functional form (`length(xs)`, etc.). Non-list operands raise `N3-3200`; sorting incomparable elements raises `N3-3204`; `sum` requires numeric lists (`N3-3203`).
  - Filtering and mapping: `all xs where item > 1`, `all user.email from users`, plus `filter(xs, where: ...)` and `map(xs, to: ...)`. Predicates must be boolean (`N3-3201`); `map` requires list sources.
- Records:
  - Literal dictionaries `{ key: expr, ... }` with identifier or string keys.
  - Field access via `record.field`; missing fields raise `N3-3300`, invalid keys raise `N3-3301`.
- User input:
  - Single prompt: `ask user for "Label" as name` with optional validation block (`type is text|number|boolean`, `must be at least <expr>`, `must be at most <expr>`). Missing or invalid validation rules raise `N3-5000` / `N3-5001`.
  - Forms: `form "Label" as signup:` followed by `field "Label" as name` lines, each with optional validation. Duplicate field identifiers raise `N3-5011`; invalid rules raise `N3-5012`.
  - When provided, answers are bound into the variable environment; otherwise, pending input definitions are recorded for the runtime to surface.
- Logging and observability:
  - Logs: `log info|warning|error "Message"` with optional metadata record (`with { key: value }`). Invalid levels raise `N3-5100`; messages must be string literals (`N3-5101`).
  - Notes: `note "Message"` annotate the trace.
  - Checkpoints: `checkpoint "label"` mark milestones (`N3-5110` on non-string labels).
- Helpers and functions:
  - Define at top level: `define helper "name":` with optional `takes` parameters and optional `returns` name. Body supports statements and `return [expr]`.
  - Calls: `<identifier>(arg, ...)` inside expressions. Unknown helpers raise `N3-6000`; arity mismatches raise `N3-6001`; using `return` outside a helper raises `N3-6002`; duplicate helper identifiers raise `N3-6003`.
- Modules/imports:
  - `use module "name"` loads a module; `from "name" use helper|flow|agent "item"` records specific imports. Missing modules or symbols produce `N3-6100`/`N3-6101`; duplicate imports `N3-6103`.
- Settings/environments:
  - Top-level `settings:` with nested `env "name":` blocks containing `key be expr` entries. Duplicate envs raise `N3-6200`; duplicate keys inside an env raise `N3-6201`.
  - Optional `theme:` block: `<token> color be "<value>"` entries define UI theme tokens (e.g., `primary`, `accent`) for use in styling.
- Frames (data sources):
  - Legacy and English forms are equivalent:
    - `frame "documents": backend "default_db" table "documents"`
    - `frame is "documents": backend is "default_db" table is "documents"`
  - Additional fields: `primary_key`, `select`, `where`, CSV options (`with delimiter ","`, `has headers`).
- Vector stores (RAG foundations):
  - Declare a semantic index over a frame:
    - `vector_store "kb": backend "default_vector" frame "documents" text_column "content" id_column "id" embedding_model "default_embedding"`
    - or English style: `vector_store is "kb": backend is "default_vector" frame is "documents" text_column is "content" id_column is "id" embedding_model is "default_embedding"`
  - The embedding model resolves through the multi-provider registry (must be an embedding model).
  - Backends may be in-memory or external (e.g., pgvector) depending on configuration.
  - Ingestion/indexing: `vector_index_frame` flow steps embed `text_column` from the attached frame (optionally filtered with `where`) and upsert vectors keyed by `id_column` into the vector backend. Both classic and English forms are equivalent:
    - `kind "vector_index_frame" vector_store "kb" [where: ...]`
    - `kind is "vector_index_frame" vector_store is "kb" [where: ...]`
  - Retrieval (RAG query): `vector_query` flow steps embed a query, run similarity search, and return matches plus a concatenated `context` string you can pass to an AI step:
    - `kind "vector_query" vector_store "kb" query_text state.question top_k 5`
    - or English form: `kind is "vector_query" vector_store is "kb" query_text is state.question top_k 5`
  - Typical pattern: index documents with `vector_index_frame`, then in a flow run `vector_query` and feed `step "retrieve" output.context` into an `ai` step alongside the user question.
- UI pages & layout:
  - `page "name" at "/route":` defines a UI page. Layout elements: `section`, `heading`, `text`, `image`, `use form`, `state`, `input`, `button`, `when ... show ... otherwise ...`.
  - Styling directives inside pages/sections/elements: `color is <token|string>`, `background color is ...`, `align is left|center|right`, `align vertically is top|middle|bottom`, `layout is row|column|two columns|three columns`, `padding|margin|gap is small|medium|large`.
  - Class/inline styling on components: every layout element may declare `class is "<classes>"` and a `style:` map of string key/value pairs. Example:
    ```
    text is "title":
      value is "Welcome"
      class is "hero-title"
      style:
        color: "#ffffff"
        background: "#1a73e8"
    button is "cta":
      label is "Get Started"
      class is "primary-cta"
      style:
        padding: "12px 24px"
        border_radius: "8px"
      on click:
        navigate to "/start"
    ```
    - `class` is a string literal (may include multiple class tokens).
    - `style:` holds string literal pairs for inline styling; the manifest surfaces these as `className` and `style` for Studio rendering.
  - Reusable UI components: `component "Name": [takes params] render: <layout>`, invoked inside pages as `<Name> <expr>:` with optional named argument blocks matching declared parameters.
- UI rendering & manifest:
  - UI manifest v1 captures pages, routes, layout trees, styles, state, components, and theme tokens for frontend rendering.
  - Backend bridge exposes `/api/ui/manifest` and `/api/ui/flow/execute` to let the frontend render pages and call flows with state/form data.

## Loops
- Flow-level for-each loops: `for each is <var> in <expr>:` (or `for each <var> in <expr>:`) inside a `flow` block. The indented body contains normal flow steps and runs once per element in the iterable. Iterables resolving to `None` are treated as empty; non-list/array-like values raise a flow error (“loop iterable must be a list/array-like”). The loop variable is available inside the body (including `when` conditions) and is not guaranteed to exist outside the loop.
- Script for-each loops: `repeat for each <name> in <expr>:` followed by a block of statements. The iterable must evaluate to a list (`N3-3400`).
- Bounded loops: `repeat up to <expr> times:`; the count must be numeric and non-negative (`N3-3401` / `N3-3402`).
- Loops execute inside flow/agent script blocks and share the current variable environment.

## Real-Time State Updates
- `set state.<field> be <expr>` mutates flow state. The runtime emits a `state_change` stream event with the `path`, `old_value`, and `new_value` whenever state changes.
- The reference server exposes `/api/ui/state/stream` (JSON lines) that carries these `state_change` events for live UI previews.
- `/api/ui/flow/stream` also includes `state_change` events for the associated flow run; the Studio preview combines this with `state/stream` for continuous synchronization.
- UI components bound to `state.*` update immediately when a corresponding `state_change` event arrives—no manual refresh needed.

## Diagnostics Philosophy
- Categories: `syntax`, `semantic`, `lang-spec`, `performance`, `security`.
- Severities: `info`, `warning`, `error`.
- Core codes (see docs/diagnostics.md for full list):
  - `N3-1001`: missing required field
  - `N3-1002`: unknown field
  - `N3-1003`: invalid child block
  - `N3-1004`: duplicate name in scope
  - `N3-1005`: type/value mismatch
  - `N3-2001`: unknown reference (ai/agent/model/memory, etc.)
- Strict mode (when enabled by callers) may treat warnings as errors; otherwise, errors halt compilation while warnings are advisory.
