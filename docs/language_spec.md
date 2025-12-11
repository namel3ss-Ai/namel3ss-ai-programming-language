# Namel3ss Language Specification (V3)

This document describes the Namel3ss V3 language as it exists today. It mirrors the current lexer/parser/IR and the validation rules enforced at runtime. No grammar changes are introduced here; all constraints are enforced via validation and diagnostics.

Naming & variables follow **Naming Standard v1** (`docs/language/naming_v1.md`). The English-style surface is now frozen for the 1.0 line: headers use `is`, assignments use `be`, and legacy symbolic forms have been removed. See the walkthrough in `docs/book/variables_and_scope.md` and the guidance in `docs/language/style_guide.md` and `docs/language/lint_rules.md`.
- For migrating legacy sources, use `n3 migrate naming-standard` (see `docs/language/migrating_to_english_syntax.md`).

## Data & Collections
- Core shapes: lists, records, frames (tabular rows), and collection pipelines attached to `let` bindings.
- Pipelines support: `keep/drop rows where ...`, `group by ...: let ...`, `sort rows/groups by ... [descending]`, `take/skip first N`.
- Aggregates: `sum/mean/minimum/maximum/count of list` (numeric lists for all except `count`).
- Records: destructuring in `let`/loops, safe helpers `get record.field otherwise ...`, `has key "field" on record`, strict field access with rich diagnostics.
- List helpers: `append`, `remove`, `insert` return new lists (no mutation).
- Legacy `all ... from ...` / `map(...)` syntax is rejected; use pipelines. See `docs/language/data_collections.md` and `docs/book/data_and_collections.md`.

## Control Flow

Control structures are English-first: `if` / `otherwise if` / `else`, `match` / `when` / `otherwise`, loops (`repeat for each`, `repeat up to N times`, flow-level `for each`), `retry up to N times [with backoff]`, `on error`, and core step kinds (`script`, `ai`, `agent`, `tool`). See `docs/language/control_flow.md` for the Control Flow v1 spec, examples, and out-of-scope items.

Step kinds:
- `script` is the default when `kind` is omitted on a step with script statements; it runs DSL logic (let/set, if/match, loops, retry, tool/ai/agent calls you place inside).
- `ai`, `agent`, and `tool` require a `target` and surface English errors if the target is missing or not registered.
- There is no `kind is "set"`; unsupported kinds yield a clear error listing the supported built-ins.
- `guard CONDITION:` is available as a precondition helper; it runs its body only when the condition is false and shares the same boolean checks as `if`.

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
  - optional: (none)

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
  - statements: `let` / `let constant` for locals, `set state.*` for state updates (preferred English form per Naming Standard v1).
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
  - required: `frame is "name":` with a `source:` block using either `from file "path.csv"` **or** `backend is "memory" | "sqlite" | "postgres"` plus `table is "name"`.
  - optional: `select:` with `columns are ["col1", "col2"]`; `where:` block using boolean expressions such as `row.status is "active"`.
  - semantics: loads tabular data lazily, applies optional `where` filters and `select` projections, and behaves like a list of record rows in expressions, filters/maps, aggregates, and loops.
- **macro**
  - required: `name`, `using ai "<model>"`, `description`
  - optional: `sample`, `parameters`
  - semantics: defines a macro that expands to Namel3ss code when invoked with `use macro "name"` (optionally with arguments). If an AI callback is available it is used; otherwise the `sample` string is treated as a template and `{Param}` placeholders are replaced with argument values. Expansions are parsed, linted, and merged at load-time.
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
- Variables: `let <name> be <expression>` declares a variable in the current flow/agent scope. Redeclaring in the same scope is an error.
- Constants: `let constant <name> be <expression>` declares an immutable local.
- Mutation: `set state.<name> be <expression>` updates flow/page state. Assigning to an undefined local with `set` is an error.
- Frames: frame values behave like lists of record rows in collection pipelines (`keep/drop rows`, `group by`, `sort`, `take/skip`) and loops (`repeat for each row in sales_data`).
- Macros: `use macro "name"` expands code at load-time. If AI is configured it generates code; otherwise the `sample` string is used as a template where `{ParamName}` placeholders are replaced with evaluated argument values. Advanced AI macros may return a structured `{"macro_plan": {...}}` JSON instead of raw DSL; the macro engine converts that plan into deterministic Namel3ss declarations (records/flows/pages) before running the usual parse/lint steps.
- Built-in AI macro `crud_ui` generates CRUD flows, forms, and UI pages for an entity:
  ```
  use macro "crud_ui" with:
    entity "Product"
    fields:
      field is "name":
        type is "string"
        required is true
      field is "price":
        type is "float"
        required is true
        min is 0
      field is "is_active":
        type is "bool"
        default is true
  ```
  The macro emits a frame, a `record is "Product"` declaration (with a generated UUID product_id), CRUD flows (`list_products`, `create_product`, `edit_product`, `delete_product`, `get_product`), and scaffold pages (`products_list`, `product_create`, `product_edit`, `product_detail`) that wire buttons to the generated flows using the provided fields (type/required/default/min/max).
- Built-in macro `app_scaffold` builds on `crud_ui` to emit a full app skeleton (CRUD data model + flows/pages, a simple RAG vector_store/pipeline, a support AI/agent, and a starter RAG evaluation block) from the same `entity`/`fields` block.
- UI pages: `page is "name" at "/route":` with layout elements for static rendering; sections group layout children; `use form` embeds previously declared forms. UI-2 adds `state`, `input "label" as var [type is ...]`, `button "Label": on click: ...`, and conditional blocks `when <expr>: show: ... otherwise: ...`.
- Literals: strings, booleans (`true`/`false`), and numbers (int/float).
- Macro arguments support literal values (strings, numbers, booleans, lists); variables or function calls are not supported in this phase.
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
  - English: `any var in list where predicate`
  - Functional: `any(list, where: predicate)`
  - Diagnostics: `N3-4200` any requires list, `N3-4201` predicate must be boolean.
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

### Memory Profiles & Friendly Defaults

Reusable memory configuration now lives in top-level **memory profile** blocks:

```
memory profile is "conversational_short":
  kinds:
    short_term

memory profile is "long_user_profile":
  kinds:
    profile:
      store is "user_profiles"
      extract_facts is true
```

- `short_term` under `kinds` can be written as a bare identifier or as `short_term:` with no nested fields; both forms enable a friendly default (window `20`, scope `per_session`, and a matching recall rule).
- Namel3ss recognizes five canonical kinds: `short_term`, `long_term`, `episodic`, `semantic`, and `profile`. Any typo produces a suggestion (`Memory kind "shortterm" is not supported. Did you mean "short_term"-`).
- `long_term`, `episodic`, `semantic`, and `profile` may omit `store` for local experiments; production apps usually point them at dedicated stores.

AI blocks can reference any number of profiles and optionally add an inline override block. Profiles are merged in declaration order, and inline `memory:` overrides win last:

```
ai is "support_bot":
  model is "gpt-4.1-mini"
  use memory profile "conversational_short"
  use memory profile "long_user_profile"
  memory:
    kinds:
      short_term:
        window is 32
```

- `use memory profile "name"` lines may appear anywhere inside the AI block. Referencing an unknown profile raises `I can’t save this AI because it uses memory profile "name" but no such profile is declared.` (`IRError`).
- An ai may list many profiles but **only one** inline `memory:` block; multiple blocks trigger `N3L-802` with a friendly English hint.
- If the merged profiles do not define any kinds or recall rules, the compiler raises an error explaining how to add `kinds:` or `recall:` entries.

Diagnostics stay consistent across English and legacy forms:

- `N3L-1201` now reports `AI "support_bot" refers to memory store "missing_store", but that store is not configured. Add it to your configuration file, or change the store name to one of the configured stores.`
- `N3L-1202` messages call out the offending field (window, retention_days, pipeline `max_tokens`, etc.) and remind you that the value must be a positive integer.

### Multi-kind memory and recall rules

Each canonical kind carries a built-in mental model and defaults:

- **short_term** - working memory for the current session. Defaults to window `20`, scope `per_session`, and auto-injects a `short_term` recall rule when none is present.
- **long_term** - durable transcript snippets. Defaults to scope `per_user` (falling back to `per_session` when no user id is available) and applies `top_k` recall with a default of `5`.
- **episodic** - important episodes/events. Defaults to scope `per_user`, retention `365` days, and `top_k` recall (default `5`).
- **semantic** - knowledge and documents. Defaults to scope `shared` with `top_k` recall (default `8`).
- **profile** - structured user facts. Defaults to scope `per_user`, `extract_facts false`, and uses an `include` flag (default `true`) instead of `count`/`top_k`.

Example:

```
ai is "travel_planner":
  model is "gpt-4.1-mini"
  memory:
    kinds:
      short_term
      episodic:
        store is "trip_episodes"
        retention_days is 365
      semantic:
        store is "travel_kb"
      profile:
        store is "user_profiles"
        extract_facts is true
    recall:
      - source is "short_term"
        count is 16
      - source is "episodic"
        top_k is 10
      - source is "semantic"
        top_k is 8
      - source is "profile"
        include is true
```

- Recall `source` must be one of the canonical kinds; typos raise `N3L-1202` with a suggestion.
- Referencing a kind that was not declared under `kinds:` raises `N3L-1202` with guidance to add the missing entry.
- `include` is only valid with `profile`; using it elsewhere produces `N3L-1202` explaining how to fix the rule.

### Memory Pipelines

Any memory kind can declare a pipeline of English-first steps that run after each AI call:

```
ai is "support_bot":
  model is "gpt-4.1-mini"
  memory:
    kinds:
      short_term:
        pipeline:
          step is "summarise_short_term":
            type is "llm_summariser"
            max_tokens is 512
            target_kind is "episodic"
      profile:
        store is "user_profiles"
        pipeline:
          step is "extract_profile_facts":
            type is "llm_fact_extractor"
      semantic:
        store is "semantic_kb"
        pipeline:
          step is "prepare_semantic_vectors":
            type is "vectoriser"
            embedding_model is "travel-embed"
```

- `pipeline:` introduces one or more `step is "name":` blocks. Every step must declare `type is "..."` and may include extra fields (`max_tokens`, `target_kind`, `embedding_model`) depending on the type.
- Supported types in this phase:
  - `llm_summariser` — summarises the source kind (usually short_term) and stores the result in another kind. `target_kind` defaults to `long_term` or `episodic` if defined, falling back to the source kind. `max_tokens` defaults to 512.
  - `llm_fact_extractor` — extracts durable user facts and writes them to the profile store. If `target_kind` is omitted it automatically uses `profile`.
  - `vectoriser` — prepares conversational snippets for semantic/RAG storage. Specify `target_kind` (defaults to the source kind) and `embedding_model`.
- Pipelines run in declaration order per kind. Unknown step names, types, or invalid target kinds raise `N3L-1203` during compilation with actionable English errors.
- Summaries, profile facts, and vectorised snippets become available to recall rules in subsequent turns, so memory stays concise without manual intervention.

### Memory Policies: Scope, Retention, PII, and Decay

Every memory kind can describe how entries are shared, how long they live, how sensitive data is scrubbed, and how recency influences recall:

```
ai is "support_bot":
  model is "gpt-4.1-mini"
  memory:
    kinds:
      short_term:
        scope is "per_session"

      episodic:
        store is "chat_episodes"
        scope is "per_user"
        retention_days is 365
        time_decay:
          half_life_days is 30

      semantic:
        store is "support_kb"
        scope is "shared"

      profile:
        store is "user_profiles"
        scope is "per_user"
        pii_policy is "strip-email-ip"
```

- **scope** — one of `per_session`, `per_user`, or `shared`. Short-term defaults to per-session. Long-term, episodic, and profile default to per-user when a user id is available (and fall back to per-session with a diagnostic note if it is not). Semantic memory defaults to `shared`.
- **retention_days** — positive integer; entries older than the window are filtered during recall and pruned by the runtime vacuum helper. Defaults: short_term (7), long_term (365), episodic (365), semantic (365). Profile entries do not expire unless you specify a value.
- **pii_policy** — `none` (default) or `strip-email-ip`. When set, memory saves only scrubbed turns, summaries, and facts so emails/IP addresses never persist.
- **time_decay** — optional block for kinds recalled via `top_k`. Declare `half_life_days` to give newer entries a higher score even if they were appended earlier than stale items.

Studio's Memory Inspector surfaces each kind’s scope, retention horizon, PII policy, and decay settings (plus any per-user fallbacks) so you can verify policy behaviour at runtime.

### Inspecting and Debugging Memory

Namel3ss ships with first-class tooling so you can see memory plans and the actual entries that will be recalled for a given AI.

- **Studio Memory Inspector** ƒ?" In the Studio sidebar, open the “Memory Inspector” tab, pick an AI, and either select a recent session or type a user id. The panel shows:
  - Per-kind configuration (scope, retention days, PII policy, time_decay, and pipeline steps) pulled directly from the IR plan.
  - Current stored entries for each enabled kind, already scrubbed according to the configured `pii_policy`.
  - The effective recall plan plus the most recent recall snapshot, including per-kind diagnostics (how many items were selected, whether scopes fell back, and the decayed scores used for top_k recalls).
  - A read-only experience—no destructive buttons—so you can safely inspect production sessions.
- **CLI snapshot** ƒ?" Run `n3 memory-inspect --file app.ai --ai support_agent --session-id sess-123` to print a JSON document containing the plan plus the scrubbed state for that session. Use `--user-id user-123` for per-user scopes and `--plan-only` to print just the configuration.
  - The CLI command shares the same helper as Studio, so both outputs stay consistent and respect scope/PII policies.

If you want to script diagnostics, you can also hit the FastAPI endpoints exposed by `n3 serve`:

- `/api/memory/ai/<ai>/plan` returns the per-kind plan and recall rules.
- `/api/memory/ai/<ai>/state?session_id=...&user_id=...` returns the scrubbed entries plus the last recall snapshot for the requested context.

All of these surfaces honour the configured scopes, retention filtering, and PII scrubbing so you can safely share snapshots when debugging with teammates.

- Pattern matching:
  - `match <expr>:` with `when <pattern>:` branches and optional `otherwise:`.
  - Patterns may be literals, comparisons, or success/error bindings (`when success as value:` / `when error as err:`).
  - Diagnostics: `N3-4300` invalid pattern, `N3-4301` missing match value, `N3-4302` incompatible pattern type, `N3-4400` misuse of success/error patterns.
- Retry:
  - `retry up to <expr> times:` with optional `with backoff`.
  - Count must be numeric and at least 1 (`N3-4500` / `N3-4501`).
- Collections:
  - List literals `[a, b, c]`, indexing `xs[0]`, slicing `xs[1:3]`, prefix/suffix slices `xs[:2]` / `xs[2:]`. Negative indices are supported (Python-style): `xs[-1]`, `xs[-3:-1]`, `xs[:-2]`. Out-of-bounds indexing raises `N3-3205`.
  - List helpers: `append xs with v`, `remove v from xs` (first occurrence), `insert v at i into xs` (0-based). Non-list operands raise `N3-3200`; invalid indices raise `N3-3206`.
  - Aggregates: `sum/mean/minimum/maximum/count of xs`; numeric lists required except for `count`; empty lists error for mean/min/max; incomparable values error for min/max.
  - Collection pipelines on lists or frames: `let result be source: keep/drop rows where ...; group by ...: let ...; sort rows/groups by ... [descending]; take/skip first N`. Conditions must be boolean (`N3-3201`); sorting incomparable elements raises `N3-3204`.
- Records:
  - Literal dictionaries `{ key: expr, ... }` with identifier or string keys.
  - Field access via `record.field`; missing fields raise `N3-3300` with available-key suggestions; invalid keys raise `N3-3301`.
  - Destructuring in lets/loops: `let { name, email } be user`, `repeat for each { name, total } in rows:`.
  - Safe helpers: `get user.email otherwise "unknown"`, `has key "email" on user`.
  - Record queries use English `find <alias> where:` with operators `is`, `is not`, `is greater than`, `is less than`, `is at least`, `is at most`, `is one of`, `is null`, `is not null`. Sorting/pagination use `order <alias> by field [ascending|descending]`, `limit <alias> to N`, `offset <alias> by N`. Missing sort fields and invalid pagination values raise English diagnostics.
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
  - English-only surface:
    - File source: 
      ```
      frame is "documents":
        source:
          from file "documents.csv"
          has headers
          delimiter is ","
        select:
          columns are ["id", "title", "content"]
        where:
          row.title is not null
      ```
    - Backend source:
      ```
      frame is "orders":
        source:
          backend is "postgres"
          url is env.DATABASE_URL
          table is "orders"
      ```
  - Optional: `select:` to project specific columns; `where:` block must be boolean. Supported backends: memory, sqlite, postgres.
- Vector stores (RAG foundations):
  - Declare a semantic index over a frame:
    ```
    vector_store is "kb":
      backend is "memory"  # or "pgvector"/"faiss"
      frame is "documents"
      text_column is "content"
      id_column is "id"
      embedding_model is "default_embedding"
      metadata_columns are ["title"]
    ```
  - The embedding model must be an embedding-capable model. Supported backends: memory, pgvector, faiss.
  - Ingestion/indexing: 
    ```
    step is "index":
      kind is "vector_index_frame"
      vector_store is "kb"
      where:
        row.category is "faq"
    ```
  - Retrieval (RAG query):
    ```
    step is "retrieve":
      kind is "vector_query"
      vector_store is "kb"
      query_text is state.question
      top_k is 5
    ```
    Returns `matches` and `context` you can pass to an AI step.
- RAG pipelines (declarative retrieval flows):
  - Top-level reusable pipeline:
    ```
    rag pipeline is "support_kb":
      use vector_store "kb"
      stage is "rewrite_query":
        type is "ai_rewrite"
        ai is "rewrite_ai"
      stage is "retrieve":
        type is "vector_retrieve"
        top_k is 10
      stage is "answer":
        type is "ai_answer"
        ai is "qa_ai"
    ```
  - Stage palette:
    - `ai_rewrite` (requires `ai`), rewrites the incoming question.
    - `multi_query` (requires `ai`, optional `max_queries`, default 4) generates alternate query strings; `vector_retrieve` will fan out across them.
    - `query_decompose` (requires `ai`, optional `max_subquestions`, default 3) generates subquestions; `vector_retrieve` runs once per subquestion.
    - `query_route` (requires `ai` and `choices are ["..."]`) chooses one or more vector stores; downstream `vector_retrieve` uses the routed stores when no explicit `vector_store` is set.
    - `vector_retrieve` (requires `vector_store` or pipeline default, unless routed) with optional `top_k` (default 5) and optional `where:` metadata filter. When `queries`/`subquestions` are present, it retrieves for each and aggregates matches.
    - `ai_rerank` (requires `ai`) with optional `top_k`.
    - `fusion` (requires `from stages are ["retrieve_a", ...]`, optional `top_k`, default 5, optional `method is "rrf"`) merges matches from earlier retrieval stages.
    - `context_compress` with optional `max_tokens`.
    - `ai_answer` (requires `ai`) to produce the final answer.
  - Invoke from a flow with `rag_query`:
    ```
    step is "answer":
      kind is "rag_query"
      pipeline is "support_kb"
      question is state.question
    ```
    Missing `pipeline`, unknown pipelines, or non-string `question` values surface clear errors at validation or runtime.
  - Advanced pipeline example with query expansion and fusion:
    ```
    rag pipeline is "fusion_kb":
      use vector_store "kb"
      stage is "expand":
        type is "multi_query"
        ai is "rewrite_ai"
        max_queries is 4
      stage is "retrieve":
        type is "vector_retrieve"
        top_k is 6
      stage is "fusion":
        type is "fusion"
        from stages are ["retrieve"]
        top_k is 5
      stage is "answer":
        type is "ai_answer"
        ai is "qa_ai"
    ```

- RAG evaluation:
  - Declare an evaluation that ties a pipeline to a dataset frame:
    ```
    rag evaluation is "support_eval":
      pipeline is "support_kb"
      dataset:
        from frame "eval_questions"
        question_column is "question"
        answer_column is "expected_answer"
      metrics:
        - context_relevance
        - answer_faithfulness
        - answer_completeness
    ```
  - `dataset:` uses a frame for questions and optional expected answers. Metrics default to the three listed above when `metrics` is omitted.
  - Run with `n3 rag-eval support_eval --file path/to/file.ai`; use `--limit N` to subset rows or `--output json` to see full row metrics.
- UI pages & layout:
  - `page is "name" at "/route":` defines a UI page. Layout elements: `section`, `heading`, `text`, `image`, `use form`, `state`, `input`, `button`, `when ... show ... otherwise ...`.
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

## Constraints & Relationships v1

- `must be unique` and `must be unique within "Scope"` declare global or scoped uniqueness beyond the primary key.
- `references "OtherRecord"` marks foreign-key fields whose non-null values must point at existing records.
- `relationship is "OtherRecord" by field_name` defines non-persisted helpers for loading related records.
- `with users for each order by user_id` (plus optional projections) enriches `find <alias> where:` results with related data.
- Field validations:
  - `must be present` (alias for `required`), `must be at least ...`, `must be at most ...` on numeric fields (`int`, `float`, `decimal`).
  - `must have length at least/at most ...` on strings and arrays.
  - `must be one of [ ... ]` for enums on scalar fields.
  - `must match pattern "..."` (regular expressions) for strings.
  - Additional field types: `decimal`, `array`, `json`.
- The parser and runtime enforce these directives today (C2-C7). Every `db_create` / `db_update` / bulk helper runs through the same constraint pipeline, and `transaction:` blocks roll back all record writes when any constraint fails.

## Loops
- Flow-level for-each loops: `for each is <var> in <expr>:` (or `for each <var> in <expr>:`) inside a `flow` block. The indented body contains normal flow steps and runs once per element in the iterable. Iterables resolving to `None` are treated as empty; non-list/array-like values raise a flow error ("loop iterable must be a list/array-like"). The loop variable is available inside the body (including `when` conditions) and is not guaranteed to exist outside the loop.
- Script for-each loops: `repeat for each <name> in <expr>:` followed by a block of statements. The iterable must evaluate to a list (`N3-3400`). Use `let <name> be ...` / `let constant <name> be ...` for locals and `set state.*` for state mutation (per Naming Standard v1).
- Bounded loops: `repeat up to <expr> times:`; the count must be numeric and non-negative (`N3-3401` / `N3-3402`).
- Loops execute inside flow/agent script blocks and share the current variable environment.

## Real-Time State Updates
- `set state.<field> be <expr>` mutates flow state. The runtime emits a `state_change` stream event with the `path`, `old_value`, and `new_value` whenever state changes.
- The reference server exposes `/api/ui/state/stream` (JSON lines) that carries these `state_change` events for live UI previews.
- `/api/ui/flow/stream` also includes `state_change` events for the associated flow run; the Studio preview combines this with `state/stream` for continuous synchronization.
- UI components bound to `state.*` update immediately when a corresponding `state_change` event arrives - no manual refresh needed.

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
