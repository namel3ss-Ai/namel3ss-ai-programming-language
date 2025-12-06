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
  - references: `model_name` must reference a declared `model`.

- **agent**
  - required: `name`
  - optional: `goal`, `personality`

- **flow**
  - required: `name`
  - optional: `description`
  - children: ordered `step`s with `kind` in `{ai, agent, tool}` and a `target`.
  - references: `ai`/`agent` targets must exist; tool targets must be registered/builtin.

- **memory**
  - required: `name`, `memory_type` (one of `conversation`, `user`, `global`)

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
- Pattern matching:
  - `match <expr>:` with `when <pattern>:` branches and optional `otherwise:`.
  - Patterns may be literals, comparisons, or success/error bindings (`when success as value:` / `when error as err:`).
  - Diagnostics: `N3-4300` invalid pattern, `N3-4301` missing match value, `N3-4302` incompatible pattern type, `N3-4400` misuse of success/error patterns.
- Retry:
  - `retry up to <expr> times:` with optional `with backoff`.
  - Count must be numeric and at least 1 (`N3-4500` / `N3-4501`).
- Collections:
  - List literals `[a, b, c]`, indexing `xs[0]`, slicing `xs[1:3]`, prefix/suffix slices `xs[:2]` / `xs[2:]`. Negative indices are not yet supported. Out-of-bounds indexing raises `N3-3205`.
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

## Loops
- For-each loops: `repeat for each <name> in <expr>:` followed by a block of statements. The iterable must evaluate to a list (`N3-3400`).
- Bounded loops: `repeat up to <expr> times:`; the count must be numeric and non-negative (`N3-3401` / `N3-3402`).
- Loops execute inside flow/agent script blocks and share the current variable environment.

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
