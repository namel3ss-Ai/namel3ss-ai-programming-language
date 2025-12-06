# Namel3ss Language Specification (V3)

This document describes the Namel3ss V3 language as it exists today. It mirrors the current lexer/parser/IR and the validation rules enforced at runtime. No grammar changes are introduced here; all constraints are enforced via validation and diagnostics.

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
