# English-style Syntax for Namel3ss

Namel3ss now supports a more readable, English-inspired surface syntax. The new style is fully backward compatible with the existing syntax and compiles to the same AST/IR and runtime behavior.

Preferred usage, style, and deprecation notes live in `docs/language/style_guide.md`; the lint rules that reinforce the style are listed in `docs/language/lint_rules.md`.

## Complete Example

```ai
remember conversation as "support_history"

use model "support-llm" provided by "openai"

ai "classify_issue":
  when called:
    use model "support-llm"
    input comes from user_input
    describe task as "Classify the user's support request."

agent "support_agent":
  the goal is "Provide a clear, helpful support answer."
  the personality is "patient, concise, calm"

flow "support_flow":
  this flow will:

    first step "classify request":
      do ai "classify_issue"

    then step "respond to user":
      do agent "support_agent"

    finally step "log interaction":
      do tool "echo" with message:
        "User request was processed and logged."

app "support_bot_app":
  starts at page "support_home"
  description "A simple support assistant with memory and classification."

page "support_home":
  found at route "/support"
  titled "Support Assistant"

  section "introduction":
    show text:
      "Welcome! Describe your issue and let the assistant help."

  section "chat":
    show form asking:
      "Describe your issue (login, billing, errors)."
```

## Mapping to Core Concepts

- `remember conversation as "name"` → conversation memory declaration.
- `use model "name" provided by "provider"` → model definition.
- `ai "name": when called: ...` → AI block with `model`, `input`, and optional `description`.
- `agent "name": the goal is "..."; the personality is "..."` → agent definition.
- `flow "name": this flow will: ... do ai/agent/tool ...` → flow with ordered steps; `first/then/finally` are readability sugar.
- `app "name": starts at page "home"` → app entry page + description.
- `page "name": found at route "/"; titled "..."` → page declaration; `show text:` / `show form asking:` map to text/form components.

## System prompts

Inside an `ai` (or `agent`) block you may set exactly one system prompt:

```ai
ai "bot":
  model "gpt-4.1"
  system "You are a helpful assistant."
  input from user_text
```

Only one `system` line is allowed per block, and it must appear inside `ai`/`agent` blocks.

## AI tools

Grant an AI access to specific tools/functions by listing them in the block:

```ai
ai "support_bot":
  model "gpt-4.1-mini"
  system "You are a helpful support assistant."
  tools:
    - "weather_api"
    - tool is "create_ticket"
      as is "open_ticket"
```

- Each entry must reference a declared tool. Missing tools trigger `N3L-1410`.
- Use `as is "alias"` to expose a friendlier function name to the model without renaming the underlying tool. Duplicate aliases raise `N3L-1411`.
- When the model asks to call a tool, the runtime executes the HTTP/JSON definition, feeds the JSON result back to the model, and finally returns the natural-language answer.
- If the provider asks for an alias that does not map to any tool, the runtime raises `N3F-972`.

Flows can override tool usage per step:

```ai
step "answer":
  kind "ai"
  target "support_bot"
  tools is "none"   # disable tools for this step (default is "auto")
```

Streaming steps do not support tools yet—using `tools is "none"` (or disabling streaming) is required for tool-enabled AIs when streaming (`N3F-975`).

## Local variables (let)

Inside flow steps you can bind locals with either operator:

```
let answer = step.ask.output
let summary be answer.summary
```

`=` and `be` are equivalent. Locals are scoped to the flow execution and must be defined before use.

## Flow state (set state.*)

Flow state is a scoped dictionary you can update as you run:

```
let answer be step.ask.output
set state.answer = answer
set state.ok be true
```

`set state.<field> = expr` and `set state.<field> be expr` are equivalent. Fields are created or updated on demand; this phase supports shallow fields like `state.answer`.

## Conditionals (if / else)

Flows can branch at runtime using `if` with an optional `else`:

```ai
flow "check":
  step "grade":
    kind "script"
    let score = step.test.output

    if score >= 50:
      set state.result be "pass"
    else:
      set state.result be "fail"
```

Conditions can read locals, state, literals, and previous step outputs. The `else` block is optional; if omitted, the flow continues when the condition is false.

## Error handling (try / catch)

Catch runtime errors and keep your flow alive:

```ai
flow "safe_call":
  step "s":
    kind "script"
    try:
      step "dangerous":
        kind "ai"
        target "bot"
    catch err:
      set state.error_message be err.message
```

The identifier after `catch` (e.g., `err`) holds a simple error object with `message` and `kind`. If the try block succeeds, the catch block is skipped.

## Loops (for each)

Iterate over a list and bind each element to a loop variable:

```ai
flow "process_items":
  let items be state.items

  for each item in items:
    set state.last_item be item
```

The right-hand expression is evaluated once and must be a list (or list-like). The loop runs sequentially over the elements. The loop variable behaves like a local inside the body; after the loop, it retains the last value according to the current execution model.

## Conversation memory

Declare a named conversation memory and attach it to an AI:

```ai
memory "support_chat":
  type "conversation"
  retention "30 days"  # optional hint

ai "support_bot":
  model "gpt-4.1-mini"
  system "You are a helpful support assistant."
  memory "support_chat"
```

When this AI is called, recent messages from `support_chat` (for the current session/request) are loaded and prepended. The new user + assistant messages are appended back to the same memory. For now, only `type "conversation"` is supported; retention is stored for future policies.

## Frames & persistence

Declare a named frame that maps to real storage (memory/sqlite/postgres) and use it from flows:

```ai
frame "conversations":
  backend "memory"
  table "conversations"

flow "store_and_load":
  step "insert":
    kind "frame_insert"
    frame "conversations"
    values:
      user_id: state.user_id
      message: state.message

  step "load":
    kind "frame_query"
    frame "conversations"
    where:
      user_id: state.user_id

  let messages be step "load" output
  set state.messages be messages
```

`frame_insert` writes a row; `frame_query` returns a list of rows, optionally filtered by equality on the fields you specify in `where`. Backends supported in this phase include `memory` and `sqlite` (with `table` specifying the target table/collection).

Updates and deletes use the same pattern:

```ai
step "rename":
  kind "frame_update"
  frame "conversations"
  where:
    user_id: state.user_id
  set:
    name: state.new_name

step "remove":
  kind "frame_delete"
  frame "conversations"
  where:
    user_id: state.user_id
```

`frame_update` requires a non-empty `set` block. `frame_delete` requires a `where` block in this phase to prevent deleting all rows accidentally. Outputs from update/delete steps are the number of affected rows.

## Record models & CRUD steps

Build typed models on top of frames and use first-class CRUD steps:

```ai
frame "documents":
  backend "memory"
  table "documents"

record "Document":
  frame "documents"
  fields:
    id:
      type "uuid"
      primary_key true
    project_id:
      type "uuid"
      required true
    title:
      type "string"
      required true
    created_at:
      type "datetime"
      default "now"

flow "manage_document":
  step "create":
    kind "db_create"
    record "Document"
    values:
      id: state.doc_id
      project_id: state.project_id
      title: state.title

  step "load":
    kind "db_get"
    record "Document"
    by id:
      id: state.doc_id

  step "rename":
    kind "db_update"
    record "Document"
    by id:
      id: state.doc_id
    set:
      title: state.new_title

  step "remove":
    kind "db_delete"
    record "Document"
    by id:
      id: state.doc_id
```

- `record` declarations tie a typed schema to an existing frame. Field types supported in this phase: `string`, `text`, `int`, `float`, `bool`, `uuid`, and `datetime`. One field must be marked `primary_key`.
- `db_create` requires a `values` block. Required (or primary-key) fields must be present unless a default is defined. Defaults can be literals or `"now"` for datetime columns.
- `db_get` returns either a single record when `by id:` is provided, or a list when using `where:` filters. Add `limit is 10` to slice the list.
- `db_update` and `db_delete` operate on a single record via the `by id:` block. `db_update` returns the updated record; `db_delete` reports `{ ok: true, deleted: 1 }` when a row was removed.

These steps reuse the existing frame backend, so records automatically persist wherever the frame points (memory, sqlite, postgres). Future phases will add migrations, relations, and richer querying.

## Backward Compatibility

The existing syntax (e.g., `memory "m":\n  type "conversation"`) remains fully supported. Formatter output continues to use the original concise style, and both styles can be mixed in the same file.

Use whichever style fits your team; new projects are encouraged to adopt the English-style syntax for readability.

## Conditions (Phase 1)

Flow steps can branch using English-style `if / otherwise` chains or simple `when` checks:

```ai
flow "support_flow":
  step "route to handler":
    if result.category is "billing":
      do agent "billing_agent"
    otherwise if result.category is "technical":
      do agent "technical_agent"
    otherwise:
      do agent "general_agent"

  step "maybe escalate":
    when result.priority is "high":
      do agent "escalation_agent"
```

See `docs/language/conditions.md` for the full set of supported operators, macros, rulegroups, patterns, bindings, and flow redirection.

## Conditional Flow Redirection

Inside a flow step (including inside condition branches), you can jump to another flow using plain English:

```ai
flow "main_flow":
  step "route":
    if result.category is "billing":
      go to flow "billing_flow"
    otherwise:
      go to flow "fallback_flow"

flow "billing_flow":
  step "finish":
    do tool "echo"
```

`go to flow "name"` ends the current flow and continues execution in the target flow. When used inside a conditional branch, only the selected branch's redirect runs, and subsequent steps in the current flow are skipped. Traces include a `flow.goto` event showing the source step and destination flow.

## Variables and Expressions (Phase 1)

Use `let <name> be <expression>` to declare variables and `set <name> to <expression>` to mutate them. The symbolic `=` form is still accepted for developers, but the English `be` / `to` style is preferred. Arithmetic can be written with symbols (`+`, `-`, `*`, `/`, `%`) or words (`plus`, `minus`, `times`, `divided by`). Comparisons support both symbols and words such as `is greater than`, `is less than`, `is at least`, and `is at most`.

Example:

```ai
flow "scoring":
  step "compute":
    let base be 10
    let bonus be 5
    let total be base plus bonus

    if total is greater than 10:
      do agent "notify"
```

Boolean expressions use `and`, `or`, and `not`, and parentheses are available for grouping. Redeclaring a variable in the same scope or assigning to an undefined variable produces a diagnostic.

## Collections, Records, and Loops (Phase 2)

Lists, records, and safe loops extend the English surface while keeping the symbolic forms available.

### Lists: literals, indexing, slicing
```ai
let xs be [1, 2, 3, 4]
let first be xs[0]
let middle be xs[1:3]
let prefix be xs[:2]
let suffix be xs[2:]
```

Negative indices are supported Python-style, so `xs[-1]` is the last item and `xs[:-1]` trims the tail. Indexing out of bounds raises a runtime error. Slices always return a new list without mutating the original.

### List built-ins and pipelines
- English style: `length of xs`, `first of xs`, `last of xs`, `sorted form of xs`, `reverse of xs`, `unique elements of xs`, `sum of xs`
- Functional equivalents: `length(xs)`, `first(xs)`, `last(xs)`, `sorted(xs)`, `reverse(xs)`, `unique(xs)`, `sum(xs)`

```ai
let xs be [3, 1, 2]
let l be length of xs          # 3
let s be sorted form of xs     # [1, 2, 3]
let total be sum(xs)           # 6
```

### Filtering and mapping
Use natural phrasing or the functional helpers:

```ai
let highs be all xs where item > 10
let emails be all user.email from users

let evens be filter(xs, where: item % 2 == 0)
let doubled be map(xs, to: item * 2)
```

Filter predicates must return booleans. Mapping evaluates the expression for each element. Both operate on lists.

### Record literals and field access
Records are inline dictionaries:

```ai
let user be { name: "Ada", age: 37 }
let name be user.name
```

Accessing a missing field raises `N3-3300`. Record keys must be identifiers or strings.

### Safe loops
- For-each: `repeat for each item in xs:` then a block
- Bounded: `repeat up to 5 times:` then a block

```ai
repeat for each score in scores:
  set total to total + score

repeat up to 3 times:
  do tool "ping"
```

Loop counts must be numeric and non-negative; for-each requires a list value.

### Example flow
```ai
flow "scoring":
  step "compute":
    let base be 10
    let bonus be 5
    let scores be [base, bonus, 7]
    let total be sum(scores)
    let over_threshold be all scores where item > 6

    repeat for each s in scores:
      set total to total + s

    if total is greater than 30:
      do agent "notify"
```

## Strings & Built-ins (Phase 3)

Common utilities stay readable:

- Strings: `trim of name`, `lowercase of code`, `uppercase of code`, `replace "foo" with "bar" in text`, `split text by ","`, `join parts with ", "`, `slugify of title`
- Functional: `trim(name)`, `lowercase(name)`, `replace(text, "foo", "bar")`, `split(text, ",")`, `join(parts, ", ")`, `slugify(title)`
- Numbers: `minimum of scores`, `maximum of scores`, `mean of scores`, `round value to 2`, `absolute value of delta`
- Functional: `min(scores)`, `max(scores)`, `mean(scores)`, `round(value, 2)`, `abs(delta)`
- Boolean helpers: `any result in results where result.score is greater than 0.8`, `all user in users where user.is_verified`
- Time/random: `current timestamp`, `current date`, `random uuid` or `current_timestamp()`, `current_date()`, `random_uuid()`

Example:

```ai
let name be "  Disan  "
let trimmed be trim of name
let slug be slugify of "Hello World"

let scores be [12, 4, 9, 10]
let minimum be minimum of scores
let average be mean of scores

let any_high be any score in scores where score is greater than 9
```

## Pattern Matching and Retry (Phase 4)

Use `match` to branch on values:

```ai
match user.intent:
  when "billing":
    do agent "billing_agent"
  when "technical":
    do agent "technical_agent"
  otherwise:
    do agent "fallback_agent"
```

Handle result shapes explicitly:

```ai
match result:
  when success as value:
    do agent "handle_success" with data: value
  when error as err:
    do agent "handle_failure" with error: err
```

## User Input, Logging, and Observability (Phase 5)

### Asking the user
Prompt for a single value and bind it to a variable:

```ai
ask user for "Email" as email
  type is text
```

If the value is already provided (e.g., via metadata), execution continues; otherwise the runtime records a pending input so UIs can collect it.

### Forms
Gather multiple fields at once and receive a record:

```ai
form "Survey" as survey:
  field "Name" as name
    type is text

  field "Age" as age
    type is number
    must be at least 18
```

After submission, `survey.name` and `survey.age` are available like any record fields.

### Logging, notes, checkpoints
- Logs: `log info "Starting checkout" with { order_id: order.id }`
- Notes: `note "Before processing survey"`
- Checkpoints: `checkpoint "after_survey"`

Logs support `info`, `warning`, and `error` levels, with optional metadata records. Notes and checkpoints annotate the trace without levels.

## Helpers, Imports, and Settings (Phase 6)

### Helpers / functions
Define reusable helpers at the top level:

```ai
define helper "normalize_score":
  takes score
  returns normalized
  let normalized be score divided by 100
  return normalized
```

Call helpers from expressions: `let adjusted be normalize_score(score)`. `return` may omit an expression to yield `null`.

### Modules and imports
- Load a module: `use module "common_helpers"`
- Import specific items: `from "billing" use helper "normalize_score"`

Imports are recorded in the IR for resolution by the host environment.

### Settings and environments
Declare environment-specific configuration:

```ai
settings:
  env "production":
    model_provider be "openai"
    log_level be "info"

  env "local":
    model_provider be "ollama"
    log_level be "debug"
```

Each `env` is a map of keys to expressions; the active environment can be selected by tooling or runtime.

Retry unstable work:

```ai
retry up to 3 times with backoff:
  do tool "fetch_remote" with url: endpoint
```

## Frames & Data

Declare reusable tabular data and query it in English:

```ai
frame "sales_data":
  from file "sales.csv"
  has headers
  select region, revenue, country

flow "be_revenue":
  step "filter":
    let be_sales be all row from sales_data where row.country is "BE"
    let total be sum of all row.revenue from be_sales

    repeat for each row in be_sales:
      log info "Row" with { region: row.region, revenue: row.revenue }
```

Frames load lazily from CSV files, optionally apply `where` filters and `select` projections, and behave like lists of records in expressions, filters/maps, aggregates, and loops.

## AI-Assisted Macros

Define high-level instructions that an AI expands into Namel3ss code:

```ai
macro "greet_user" using ai "codegen":
  description "Generate a greeting flow."

use macro "greet_user"
```

Parameterized macros accept arguments:

```ai
macro "crud_for_entity" using ai "codegen":
  description "Generate CRUD flows for an entity."
  parameters entity, fields

use macro "crud_for_entity" with:
  entity "Product"
  fields ["name", "price"]
```

The expansion is parsed, linted, validated, and merged at load-time. Expansions must be valid Namel3ss code (no backticks/HTML); oversized or recursive expansions are rejected.

### Built-in AI UI Macro: CRUD UI

Generate fullstack CRUD UI and flows in one line:

```ai
use macro "crud_ui" with:
  entity "Product"
  fields ["name", "price", "quantity"]
```

The macro produces flows (list/create/update/delete/detail), a form, and UI pages (list/create/edit/detail/delete) with state, inputs, buttons, navigation, and basic styling.

## UI Pages & Layout (Phase UI-1)

Declare static UI pages with headings, text, images, sections, and embedded forms:

```ai
page "home" at "/":
  heading "Welcome"
  text "Select an option below"

page "signup" at "/signup":
  section "form_section":
    heading "Create your account"
    use form "Signup Form"
```

Pages require a name, a route beginning with `/`, and at least one layout element. Layout elements are limited to `section`, `heading`, `text`, `image`, and `use form ...`.

## UI Interactivity & State (Phase UI-2)

Reactive state, inputs, buttons, and conditional visibility:

```ai
page "signup" at "/signup":
  state name is ""

  heading "Create your account"
  input "Your name" as name

  button "Continue":
    on click:
      do flow "register_user" with name: name

page "hello" at "/hello":
  state name is ""

  input "Your name" as name

  when name is not "":
    show:
      text "Hello, friend!"
  otherwise:
    show:
      text "Enter your name to continue."
```

Controls must live inside pages/sections. Supported input types: `text`, `number`, `email`, `secret`, `long_text`, `date`. Buttons require an `on click` handler that can `do flow ...` or `navigate to page ...`. Conditionals switch layout reactively based on expressions.

## UI Styling & Theming (Phase UI-3)

- Theme tokens in `settings`:

```ai
settings:
  theme:
    primary color be "#2563eb"
    background color be "#0b1120"
```

- Styles on elements (indent under the element) or at the container level:

```ai
page "home" at "/":
  layout is column
  padding is large

  heading "Welcome"
    color is primary

  text "Choose a path"
    align is center
```

Supported styles:
- `color is <token|string>`
- `background color is <token|string>`
- `align is left|center|right`
- `align vertically is top|middle|bottom`
- `layout is row|column|two columns|three columns`
- `padding|margin|gap is small|medium|large`

## UI Components (Phase UI-3)

Declare reusable components:

```ai
component "PrimaryButton":
  takes label, action
  render:
    button label:
      on click:
        do action
```

Use components inside pages:

```ai
page "welcome" at "/":
  PrimaryButton "Get Started":
    action:
      navigate to page "signup"
```

## UI Rendering & Fullstack Integration (Phase UI-4)

- Build a UI manifest from your `.ai` code; the manifest contains pages, routes, layout, styles, state, events, and theme tokens.
- Backend bridge endpoints:
  - `POST /api/ui/manifest` with `{ code }` → manifest JSON (versioned).
  - `POST /api/ui/flow/execute` with `{ source, flow, args }` → runs a flow with arguments collected from UI state/forms.
- Frontend consumes the manifest to render pages, bind state to inputs, dispatch click events, and navigate via `navigate to page`.
- Conditionals (`when ... show ... otherwise ...`) are evaluated reactively against UI state; styling maps to theme tokens and layout (row/column/two/three columns, spacing, alignment).

## Studio CLI (Phase 1)

Start the minimal Studio shell locally:

```bash
n3 studio
# optional overrides:
n3 studio --backend-port 9000 --ui-port 4174 --no-open-browser
```

The CLI starts the backend and a placeholder Studio UI. URLs printed:
- Primary URL: `http://namel3ss.local/studio`
- Fallback URL: `http://127.0.0.1:<ui_port>/studio`

If `namel3ss.local` does not resolve, use the fallback or add `127.0.0.1 namel3ss.local` to your hosts file.

## Studio Phase 2 — Shell Layout

`/studio` now renders the Studio shell: top bar (navigation + actions), left project sidebar, tabbed main area (Code, UI, Flow Graph), right Inspector, and bottom status bar. Content is placeholder for now:
- Code tab: “Code editor will appear here in Studio Phase 3.”
- UI tab: “Live UI preview will appear here in Studio Phase 3.”
- Flow Graph tab: “Flow graph will appear here in Studio Phase 5.”

Navigation tabs and project tree selections update labels; styling defaults to a dark theme. Later phases will wire real editors, previews, and graphs.

## Studio Phase 3 — Real Code Editor

In the Code tab, Studio now renders a real editor for `.ai` files. Select a file in the Project sidebar to load its contents, edit, and press Ctrl+S / Cmd+S to save (or rely on auto-save). Files are written to your project folder via the `/api/studio/file` endpoint. Status updates show saving/loading states; errors surface inline.

## Studio Phase 4 — Filesystem Project Explorer

The Project sidebar now reflects the actual project files on disk:
- The tree is populated from `/api/studio/files`, scanning your project root.
- Only relevant files (e.g., `.ai`) are shown; common junk dirs (`.git`, `node_modules`, etc.) are ignored.
- Clicking a file loads it into the editor; the selected path drives the Code tab header.
- Use the Refresh button in the Project header to re-scan the filesystem; current selection is preserved when possible.

## Studio Phase 5 — Live UI Preview

The UI tab now renders a live preview of your pages:
- Studio fetches the UI manifest from `GET /api/ui/manifest`.
- Selecting a `pages/*.ai` file focuses that page in the preview (fallback to the first page).
- Device modes (Desktop/Tablet/Phone) adjust the preview width; use the Refresh control to re-fetch the manifest.
- Saving changes in the Code tab triggers a manifest refresh so the preview stays in sync.

## Studio Phase 6 — Interactive Preview

- Inputs in the UI tab are editable and keep local preview state.
- Buttons execute real flows via `/api/ui/flow/execute`, passing bound arguments.
- Results (or errors) are shown in a small console panel so you can verify end-to-end flow wiring quickly.

## Studio Phase 7 — Inspector Panel

- Switch to *Inspector Mode* in the UI tab to click on any element and view metadata in the right panel.
- The Inspector shows element type, styles, bindings, events (e.g., on-click flow calls), and source file.
- Selected elements highlight in the preview; use the button to open the source in the Code tab.

## Studio Phase 8 — Navigation & Routing

- Pages expose routes from the manifest; preview now maintains a local router with back/forward controls and route display.
- Buttons with `navigate to page "name"` navigate between pages in Preview Mode; Inspector Mode prevents navigation.
- Route selection respects page routes, and history stacks allow quick multi-page simulation without touching the browser URL.

## Studio Phase 9 — Editable Inspector Properties

- In Inspector Mode, editable fields appear for text/heading, button labels, input labels, colors, layout, alignment, and spacing.
- Changes are applied via `/api/studio/code/transform`, updating the underlying `.ai` source safely, refreshing the editor and preview automatically.
- Invalid edits return clear errors; edits preserve indentation and surrounding syntax where possible.

## Studio Phase 10 — Layout & Component Editing

- Add new UI elements (heading, text, button, input, section) from the palette in Inspector Mode.
- Delete or reorder elements (move up/down) and see the changes applied to `.ai` files via `/api/studio/code/transform`.
- Preview, manifest, and code editor stay synchronized after each structural edit; navigation and flow wiring continue to work as before.

## Studio Phase 11 — AI UI Generator

- In Inspector Mode, click **AI Generate UI** to open a prompt dialog.
- Describe the layout you want; Studio calls `/api/studio/ui/generate` to insert AI-generated UI code into the current page (relative to the selected element if applicable).
- After generation, the code editor, manifest, and preview refresh automatically so you can continue editing or inspecting the new elements.

## Style & Linting (Phase 7)

- Preferred English style is captured in `docs/language/style_guide.md`.
- Core lint rules are listed in `docs/language/lint_rules.md`; run the lint engine to catch unused variables, shadowing, discouraged `=`, and more.
