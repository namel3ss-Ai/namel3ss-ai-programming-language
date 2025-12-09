# Learn Namel3ss: The AI-Native Programming Language

## Preface
Namel3ss is an English-ish DSL and runtime for building AI-native applications: UI, flows, memory, RAG, tools, records/CRUD, and auth in one `.ai` file. You describe intent; the runtime executes it; Studio lets you preview, run, and inspect. This book is for developers comfortable with coding but new to Namel3ss who want to ship assistants, RAG apps, CRUD dashboards, and tool-integrated flows.

Install with pip:
```bash
pip install namel3ss
```

## Table of Contents
1. [Introduction](#1-introduction)
2. [Getting Started: A First Namel3ss App](#2-getting-started-a-first-namel3ss-app)
3. [Core Concepts](#3-core-concepts)
4. [Variables, State, and Scope](#4-variables-state-and-scope)
5. [Flows: Logic, Conditions, and Error Handling](#5-flows-logic-conditions-and-error-handling)
6. [AI Blocks: Models, System Prompts, and Memory Hooks](#6-ai-blocks-models-system-prompts-and-memory-hooks)
7. [Memory: Conversation, Long-Term, and Profiles](#7-memory-conversation-long-term-and-profiles)
8. [Data & RAG: Frames and Vector Stores](#8-data--rag-frames-and-vector-stores)
9. [Records & CRUD: Building Data-Backed Apps](#9-records--crud-building-data-backed-apps)
10. [Tools & Function Calling: Connecting to External APIs](#10-tools--function-calling-connecting-to-external-apis)
11. [Authentication & User Context](#11-authentication--user-context)
12. [Building UIs & Navigation](#12-building-uis--navigation)
13. [Putting It All Together: End-to-End App](#13-putting-it-all-together-end-to-end-app)
14. [Appendix: Syntax Reference (from the Parser)](#14-appendix-syntax-reference-from-the-parser)

---

## 1. Introduction
Namel3ss is an AI-native language: flows orchestrate work, AI blocks define models and prompts, memory remembers conversations, frames and vector stores power RAG, records enable CRUD, tools call external APIs, and auth provides user context. Everything lives in a single readable `.ai` file that the runtime executes and Studio visualizes. Compared to traditional stacks, you write intent in a small DSL and get UI, backend, AI orchestration, and observability in one place.

Cross-reference:
- Parser surface: `src/namel3ss/parser.py`.
- Runtime foundations: `src/namel3ss/flows/engine.py`, `src/namel3ss/runtime/context.py`, `src/namel3ss/ui/manifest.py`.
- Examples: `examples/support_bot/support_bot.ai`, `examples/rag_qa/rag_qa.ai`, `examples/tools_and_ai/tools_and_ai.ai`, `examples/crud_app/crud_app.ai`.

---

## 2. Getting Started: A First Namel3ss App
A minimal app with UI, a flow, and an AI call:

```ai
app is "hello-app":
  entry_page is "home"

model is "default-model":
  provider is "openai_default"

ai is "greeter":
  model is "default-model"
  system is "Be a concise greeter."
  input from user_input

flow is "welcome":
  step is "say":
    kind is "ai"
    target is "greeter"

page is "home" at "/":
  section is "hero":
    heading is "Hello Namel3ss"
    text is "Type a greeting and click Run."
    input is "user_input":
      bind is state.user_input
    button is "Run":
      on click:
        do flow "welcome"
    text is "Result:"
    text is step.say.output
```

Run via CLI:
```bash
n3 run welcome --file hello.ai --input "Hello there!"
```
Open in Studio to preview the page, click the button, and watch the flow execute.

Cross-reference: parser (app/page/ai/flow/UI) in `src/namel3ss/parser.py`; runtime flow execution in `src/namel3ss/flows/engine.py`; UI manifest in `src/namel3ss/ui/manifest.py`; tests in `tests/test_parser_flow.py`, `tests/test_ui_pages.py`, `tests/test_flow_engine.py`; example seed in `examples/getting_started/app.ai`.

---

## 3. Core Concepts
- **Apps & Pages:** An `app` declares an `entry_page`. Pages declare routes and sections of UI.
- **Flows:** Ordered steps; each step has a `kind` (`ai`, `set`, `db_*`, `vector_*`, `tool`, `auth_*`, etc.).
- **AI Blocks:** Named models with `system` prompts, optional `memory` and `tools`.
- **Memory:** Short-term chat history, long-term summaries, and profile facts.
- **Data & RAG:** `frame` (table), `vector_store` (embeddings), `vector_index_frame` and `vector_query` steps.
- **Records & CRUD:** Typed records over frames plus `db_create/get/update/delete`.
- **Tools:** Declare HTTP JSON tools; use `kind is "tool"` steps or allow AI tool-calling.
- **Auth:** Configure user model; use `auth_register/login/logout`; access `user.*`.
- **UI:** Sections with headings, text, inputs, buttons; `on click` performs flows or navigation.

Cross-reference: parser for each construct in `src/namel3ss/parser.py`; runtime counterparts in `src/namel3ss/flows/engine.py`, `src/namel3ss/runtime/context.py`, `src/namel3ss/memory/*`, `src/namel3ss/tools/registry.py`, `src/namel3ss/runtime/auth.py`; tests across `tests/test_parser_*` and feature-specific files; examples listed above.

---

## 4. Variables, State, and Scope
- **State:** `state.foo` persists through a flow run; set via `set state.foo be ...`.
- **User:** `user.id`, `user.email` available after login when auth is configured.
- **Step outputs:** `step.load_user.output.email`.
- **Locals:** `let total be step.fetch.output.count`.
- **Loop vars:** Declared in `for each item in state.items`.
- **Roots:** `state`, `user`, `step`, `input`, `secret`, loop vars, locals. Unknown identifiers raise diagnostics (see `tests/test_variable_scope.py`).

Example:
```ai
flow is "calculate":
  step is "sum":
    kind is "set"
    set:
      state.total be state.a + state.b

  step is "store_local":
    let doubled be state.total * 2
    set state.doubled be doubled

  step is "fanout":
    for each item in state.items:
      step is "collect":
        kind is "set"
        set:
          state.collected be (state.collected or []) + [item]
```

Cross-reference: parser expression/scope rules in `src/namel3ss/parser.py`; evaluation in `src/namel3ss/runtime/expressions.py`; tests `tests/test_flow_let.py`, `tests/test_flow_set_state.py`, `tests/test_flow_loops_language.py`, `tests/test_variable_scope.py`.

---

## 5. Flows: Logic, Conditions, and Error Handling
- **Syntax:** `flow is "name":` with `step` blocks.
- **Kinds:** `ai`, `set`, `db_create/get/update/delete`, `vector_index_frame`, `vector_query`, `tool`, `auth_register/login/logout`, and control constructs.
- **Conditions:** `when <expr>` on a step.
- **Loops:** `for each item in <expr>:` containing nested steps.
- **Errors:** `on error:` with fallback steps.

Example:
```ai
flow is "process_ticket":
  step is "load_user":
    kind is "db_get"
    record is "User"
    where:
      id: user.id

  step is "maybe_assign":
    kind is "set"
    set:
      state.assignee be "support" if step.load_user.output.tier == "premium" else "triage"

  step is "notify":
    kind is "tool"
    target is "notify_slack"
    input:
      message: "New ticket from " + user.id
    when state.assignee == "support"

  on error:
    step is "fallback":
      kind is "set"
      set:
        state.error be "Ticket handling failed."
```

Cross-reference: parser flow/step/when/for/on error in `src/namel3ss/parser.py`; execution in `src/namel3ss/flows/engine.py`; tests `tests/test_flow_engine_v3.py`, `tests/test_flow_step_when.py`, `tests/test_flow_for_each.py`, `tests/test_flow_error_handler.py`, `tests/test_flow_try_catch.py`.

---

## 6. AI Blocks: Models, System Prompts, and Memory Hooks
- **Models:** `model is "name": provider is "openai_default"`.
- **AI blocks:** `ai is "name": model is "..."; system is "..."; input from state.field or inline`.
- **Streaming:** `streaming is true` plus optional stream metadata on steps.
- **Tools list:** Attach tool names for AI tool-calling (see Chapter 10).

Example:
```ai
model is "support-llm":
  provider is "openai_default"

ai is "triage_ai":
  model is "support-llm"
  system is "Classify requests into Billing, Shipping, or Auth."
  input from state.question

flow is "triage":
  step is "answer":
    kind is "ai"
    target is "triage_ai"
    streaming is true
    stream_channel is "chat"
```

Cross-reference: AI/model parsing in `src/namel3ss/parser.py`; runtime routing in `src/namel3ss/ai/registry.py`, `src/namel3ss/ai/router.py`, `src/namel3ss/runtime/context.py`; tests `tests/test_ai_system_prompt.py`, `tests/test_ai_streaming_flag.py`, `tests/test_flow_streaming_runtime.py`; examples `examples/support_bot/support_bot.ai`.

---

## 7. Memory: Conversation, Long-Term, and Profiles
- **Kinds:** `short_term`, `long_term`, `profile`.
- **Recall:** Ordered rules pulling from each kind.
- **Pipelines:** `llm_summarizer`, `llm_fact_extractor` steps for compaction/facts.
- **Policy:** `scope` (`per_session`, `per_user`, `shared`), `retention_days`, `pii_policy`.

Example:
```ai
memory is "support_memory":
  type is "conversation"

ai is "support_ai":
  model is "support-llm"
  system is "Support bot. Use recall and profile facts."
  memory:
    kinds:
      short_term:
        window is 8
      long_term:
        store is "default_memory"
        scope is "per_user"
        retention_days is 30
        pii_policy is "strip-email"
        pipeline:
          - step is "summarize"
            type is "llm_summarizer"
            max_tokens is 256
      profile:
        store is "default_memory"
        extract_facts is true
        pipeline:
          - step is "facts"
            type is "llm_fact_extractor"
    recall:
      - source is "short_term"
        count is 6
      - source is "long_term"
        top_k is 3
      - source is "profile"
        include is true
```

Cross-reference: parser memory rules `src/namel3ss/parser.py`; runtime memory stores/pipelines `src/namel3ss/memory/*`, integration `src/namel3ss/runtime/context.py`; tests `tests/test_memory_conversation.py`, `tests/test_memory_multikind.py`, `tests/test_memory_retention.py`, `tests/test_memory_inspector_api.py`; example `examples/support_bot/support_bot.ai`.

---

## 8. Data & RAG: Frames and Vector Stores
- **Frames:** Tables with backend and table name.
- **Vector stores:** Point at frames with `text_column`, `id_column`, and embedding model/provider.
- **Indexing:** `vector_index_frame` step.
- **Query:** `vector_query` step returning matches for downstream AI.

Example (ingest + answer):
```ai
frame is "docs":
  backend is "memory"
  table is "docs"

vector_store is "kb":
  backend is "memory"
  frame is "docs"
  text_column is "content"
  id_column is "id"
  embedding_model is "default_embedding"

flow is "ingest_docs":
  step is "insert":
    kind is "frame_insert"
    frame is "docs"
    values:
      id: "doc-1"
      content: "Refunds take 3-5 business days."
  step is "index":
    kind is "vector_index_frame"
    vector_store is "kb"

flow is "ask":
  step is "retrieve":
    kind is "vector_query"
    vector_store is "kb"
    query_text is state.question
    top_k is 2
  step is "answer":
    kind is "ai"
    target is "qa_ai"
```

Cross-reference: parser data/vector rules `src/namel3ss/parser.py`; runtime RAG in `src/namel3ss/runtime/vectorstores.py`, `src/namel3ss/rag/*`; tests `tests/test_vector_store_parse.py`, `tests/test_vector_index_frame.py`, `tests/test_vector_query_runtime.py`, `tests/test_vector_runtime.py`; example `examples/rag_qa/rag_qa.ai`.

---

## 9. Records & CRUD: Building Data-Backed Apps
- **Record:** Typed schema over a frame.
- **Fields:** `type`, `primary_key`, `required`, `default`.
- **CRUD steps:** `db_create`, `db_get`, `db_update`, `db_delete` with `values`, `where`, `by id`, `set`.

Example:
```ai
frame is "projects":
  backend is "memory"
  table is "projects"

record is "Project":
  frame is "projects"
  fields:
    id:
      type is "uuid"
      primary_key is true
      required is true
    owner_id:
      type is "string"
      required is true
    name:
      type is "string"
      required is true
    description:
      type is "text"

flow is "create_project":
  step is "create":
    kind is "db_create"
    record is "Project"
    values:
      id: state.project_id
      owner_id: user.id
      name: state.project_name
      description: state.project_description

flow is "list_projects":
  step is "list":
    kind is "db_get"
    record is "Project"
    where:
      owner_id: user.id

flow is "update_project":
  step is "update":
    kind is "db_update"
    record is "Project"
    by id:
      id: state.project_id
    set:
      name: state.new_name
      description: state.project_description

flow is "delete_project":
  step is "delete":
    kind is "db_delete"
    record is "Project"
    by id:
      id: state.project_id
```

Cross-reference: parser record/CRUD rules `src/namel3ss/parser.py`; runtime frames/records `src/namel3ss/runtime/frames.py`, flow execution `src/namel3ss/flows/engine.py`; tests `tests/test_records_crud.py`, `tests/test_frames_update_delete.py`; example `examples/crud_app/crud_app.ai`.

---

## 10. Tools & Function Calling: Connecting to External APIs
- **Tool declaration:** `tool is "name": kind is "http_json"; method/url/query/headers/body`.
- **Flow call:** `kind is "tool"` step with `input`.
- **AI tool-calling:** Add `tools:` list to an `ai` block; provider executes tools requested by the model.

Example:
```ai
tool is "get_weather":
  kind is "http_json"
  method is "GET"
  url is "https://api.example.com/weather"
  query:
    city: input.city

flow is "weather_now":
  step is "fetch":
    kind is "tool"
    target is "get_weather"
    input:
      city: state.city

ai is "assistant_with_tools":
  model is "support-llm"
  tools:
    - "get_weather"

flow is "chat_with_tools":
  step is "respond":
    kind is "ai"
    target is "assistant_with_tools"
```

Cross-reference: parser tool blocks and AI `tools` list `src/namel3ss/parser.py`; runtime tool registry/execution `src/namel3ss/tools/registry.py`, flow tool steps `src/namel3ss/flows/engine.py`, AI tool loop `src/namel3ss/runtime/context.py`; tests `tests/test_tool_decl_parse.py`, `tests/test_tool_flow_runtime.py`, `tests/test_ai_tool_runtime_loop.py`, `tests/test_ai_tools_list.py`; example `examples/tools_and_ai/tools_and_ai.ai`.

---

## 11. Authentication & User Context
- **Auth config:** `auth:` with `user_record`, `id_field`, `identifier_field`, `password_hash_field`.
- **Steps:** `auth_register`, `auth_login`, `auth_logout`.
- **User root:** Access `user.id`, `user.email`, etc., inside flows and UI.

Example:
```ai
frame is "users":
  backend is "memory"
  table is "users"

record is "User":
  frame is "users"
  fields:
    id:
      type is "uuid"
      primary_key is true
      required is true
    email:
      type is "string"
      required is true
    password_hash:
      type is "string"
      required is true

auth:
  backend is "default_auth"
  user_record is "User"
  id_field is "id"
  identifier_field is "email"
  password_hash_field is "password_hash"

flow is "register_user":
  step is "register":
    kind is "auth_register"
    input:
      email: state.email
      password: state.password

flow is "login_user":
  step is "login":
    kind is "auth_login"
    input:
      email: state.email
      password: state.password

flow is "logout_user":
  step is "logout":
    kind is "auth_logout"
```

Cross-reference: parser auth rules `src/namel3ss/parser.py`; runtime `src/namel3ss/runtime/auth.py`, context wiring `src/namel3ss/runtime/context.py`; tests `tests/test_auth.py`; example `examples/crud_app/crud_app.ai`.

---

## 12. Building UIs & Navigation
- **Components:** `heading`, `text`, `image`, `input`, `textarea`, `button`, layout (rows/columns/cards where present), badges/chat elements.
- **Bindings:** `bind is state.field`.
- **Actions:** In `on click`, use `do flow "name"` (optionally `with` arguments if supported) or navigation: `navigate to page "target"` or `navigate to "/route"`.
- **Conditionals/visibility:** Use `when`/`show` where supported on UI elements.

Example multi-page UI:
```ai
page is "home" at "/":
  section is "hero":
    heading is "Dashboard"
    button is "Go to projects":
      on click:
        navigate to page "projects"

page is "projects" at "/projects":
  section is "list":
    heading is "Projects"
    button is "Create":
      on click:
        do flow "create_project"
    text is "Owner: " + user.id
```

Cross-reference: parser UI/layout/navigation rules `src/namel3ss/parser.py`; UI manifest `src/namel3ss/ui/manifest.py`, runtime `src/namel3ss/ui/runtime.py`; Studio/backend `src/namel3ss/server.py`; tests `tests/test_ui_pages.py`, `tests/test_ui_button_navigate_parse.py`, `tests/test_ui_manifest_navigate.py`, `tests/test_ui_flow_execute.py`; examples `examples/support_bot/support_bot.ai`, `examples/crud_app/crud_app.ai`.

---

## 13. Putting It All Together: End-to-End App
Combine auth, CRUD, RAG, memory, tools, and UI. This sketch merges earlier snippets into one `.ai` file:

```ai
app is "support-suite":
  entry_page is "home"

model is "support-llm":
  provider is "openai_default"

ai is "support_ai":
  model is "support-llm"
  system is "Support bot that uses recall and knowledge base."
  tools:
    - "get_weather"
  memory:
    kinds:
      short_term:
        window is 6
    recall:
      - source is "short_term"
        count is 6

frame is "users":
  backend is "memory"
  table is "users"

record is "User":
  frame is "users"
  fields:
    id:
      type is "uuid"
      primary_key is true
      required is true
    email:
      type is "string"
      required is true
    password_hash:
      type is "string"
      required is true

auth:
  backend is "default_auth"
  user_record is "User"
  id_field is "id"
  identifier_field is "email"
  password_hash_field is "password_hash"

frame is "projects":
  backend is "memory"
  table is "projects"

record is "Project":
  frame is "projects"
  fields:
    id:
      type is "uuid"
      primary_key is true
      required is true
    owner_id:
      type is "string"
      required is true
    name:
      type is "string"
      required is true
    description:
      type is "text"

tool is "get_weather":
  kind is "http_json"
  method is "GET"
  url is "https://api.example.com/weather"
  query:
    city: input.city

flow is "register_user":
  step is "register":
    kind is "auth_register"
    input:
      email: state.email
      password: state.password

flow is "login_user":
  step is "login":
    kind is "auth_login"
    input:
      email: state.email
      password: state.password

flow is "create_project":
  step is "create":
    kind is "db_create"
    record is "Project"
    values:
      id: state.project_id
      owner_id: user.id
      name: state.project_name
      description: state.project_description

flow is "list_projects":
  step is "list":
    kind is "db_get"
    record is "Project"
    where:
      owner_id: user.id

flow is "ask_weather":
  step is "fetch":
    kind is "tool"
    target is "get_weather"
    input:
      city: state.city
  step is "respond":
    kind is "ai"
    target is "support_ai"

page is "home" at "/":
  section is "auth":
    input is "email":
      bind is state.email
    input is "password":
      bind is state.password
    button is "Register":
      on click:
        do flow "register_user"
    button is "Login":
      on click:
        do flow "login_user"
  section is "projects":
    input is "project_name":
      bind is state.project_name
    textarea is "project_description":
      bind is state.project_description
    button is "Create Project":
      on click:
        do flow "create_project"
    button is "Refresh List":
      on click:
        do flow "list_projects"
    text is "Projects: " + step.list.output
  section is "assistant":
    input is "city":
      bind is state.city
    button is "Ask Weather":
      on click:
        do flow "ask_weather"
    text is step.respond.output
```

Use the CLI to ingest and run flows, then open Studio for interactive UI, traces, memory, and provider status. The same building blocks scale to larger apps.

Cross-reference: parser and runtime modules from earlier chapters; tests across flows, memory, tools, auth, and UI; examples `examples/support_bot/support_bot.ai`, `examples/rag_qa/rag_qa.ai`, `examples/crud_app/crud_app.ai`, `examples/tools_and_ai/tools_and_ai.ai`.

---

## 14. Appendix: Syntax Reference (from the Parser)
- **App:** `app is "name":` then `entry_page is "page"` (fields parsed under `src/namel3ss/parser.py`).
- **Page:** `page is "name" at "/route": ...` with sections/components; navigation allowed in `on click`.
- **Sections & UI:** `section is "name":` with `heading`, `text`, `image`, `input`, `textarea`, `button`, layout (rows/columns/cards/badges/chat where supported), optional `when/show`, `class/style`.
- **Models:** `model is "name": provider is "..."`.
- **AI:** `ai is "name": model is "..."; system is "..."; input from <expr>; tools: ["tool_a"]; memory: ...; temperature/top_p if supported; streaming flags on steps.`
- **Memory:** Declare `memory is "name": type is "conversation"`; in AI `memory: kinds: short_term/long_term/profile` with `window`, `store`, `scope`, `retention_days`, `pii_policy`, `pipeline`; `recall` list.
- **Flows:** `flow is "name": step is "s": kind is "..."; when <expr>; for each <var> in <expr>: ...; on error: ...; let <local> be ...; set state.<field> be ...; read `step.<name>.output`.
- **Data & RAG:** `frame is "name": backend/table`; `vector_store is "name": frame is "..."; text_column/id_column/embedding_model`; steps `vector_index_frame`, `vector_query`.
- **Records & CRUD:** `record is "Name": frame is "..."; fields: <field>: type/primary_key/required/default`; steps `db_create`, `db_get`, `db_update`, `db_delete` with `values`, `where`, `by id`, `set`.
- **Tools:** `tool is "name": kind is "http_json"; method/url/query/headers/body`; flow step `kind is "tool"` with `input`; AI `tools` list for tool-calling.
- **Auth:** `auth:` with `user_record`, `id_field`, `identifier_field`, `password_hash_field`; steps `auth_register/login/logout`; expressions under `user.*`.
- **Providers:** per-model/AI `provider`; config in `namel3ss.config.*`; errors `N3L-1800`, `N3P-1801`, `N3P-1802`.
- **Diagnostics:** variable scope/unknown references/invalid UI placement handled in parser and diagnostics; see `tests/test_variable_scope.py`, `tests/test_ui_button_navigate_validate.py`.

See `src/namel3ss/parser.py` for authoritative grammar, runtime modules noted per chapter for semantics, tests under `tests/` for runnable expectations, and `examples/` for end-to-end templates. With these references and the English-ish `is`/`be` syntax, you can read, write, and ship real Namel3ss apps confidently.
