# Namel3ss Language Style Guide

This guide captures the preferred English-first style for writing Namel3ss programs. The lint rules reinforce these guidelines; following them keeps code readable and consistent.

## Naming Standard v1 (overview)
- `lower_snake_case` everywhere (variables, params, state keys, helpers, flows).
- Booleans start with `is_`, `has_`, `can_`, or `should_`.
- Lists are plural; loop variables are singular.
- Helpers/flows use verb phrases (`calculate_total`, `send_welcome_email`).
- Assignments use `be`: `let total be base plus bonus`; `let constant tax_rate be 0.21`; state updates use `set state.total be ...`.
- Full spec: [Naming Standard v1](../language/naming_v1.md) and the walkthrough in [Variables & Scope](../book/variables_and_scope.md).
- Migrating legacy files: see [Migrating to English Syntax](../language/migrating_to_english_syntax.md).

## Control Flow Style
- Prefer clear multi-line `if / otherwise if / else` blocks; keep conditions boolean and explicit.
- Use `match` with simple literal `when` branches; keep branches small and add an `otherwise` when possible.
- Loops: pick meaningful singular loop variables (`user` in `for each user in users:`) and avoid using loop vars outside the loop.
- `when` is only used inside `match` in v1; use `if` for standalone conditions.
- Keep retries and `on error` blocks concise; log enough context to understand failures.

## General Naming
- Prefer `lower_snake_case` for variables, parameters, and helper identifiers.
- Choose descriptive helper names, e.g., `"normalize_score"`, `"full_name"`.

## Assignments and Expressions
- Prefer English assignment: `let total be base plus bonus` instead of `let total = ...`.
- Use English comparisons where it reads naturally: `score is greater than 0.8`.
- Arithmetic can stay English for clarity: `base plus bonus`, `total divided by count`.

### Good
```ai
let total be base plus bonus
if score is greater than 0.8:
  do agent "notify"
```

### Not Recommended
```ai
let total = base + bonus
```

## Collections and Loops
- Iterate with `repeat for each item in items:`.
- Bounded repetition: `repeat up to 5 times:` with reasonable limits.
- Favor English list built-ins: `length of xs`, `sorted form of xs`.

## Frames and Data
- Name frames descriptively: `frame "sales_data": ...`.
- Prefer `has headers` plus `select` to keep row records lean.
- Filter with `all row from sales_data where ...` and aggregate with `sum of all row.revenue from sales_data`.

## Macros
- Keep macro descriptions concise and directive: “Generate CRUD flows for an entity.”
- Provide samples for few-shot quality.
- Limit parameters to simple, clear names; prefer structured argument values (lists/records) over ambiguous strings.
- Macro expansions must return clean Namel3ss code only—no Markdown/backticks.

## Pattern Matching
- Order branches from most specific to most general.
- Include an `otherwise` branch when possible.

## Helpers / Functions
- Define helpers with clear inputs/outputs:
```ai
define helper "normalize_score":
  takes score
  returns normalized
  let normalized be score divided by 100
  return normalized
```
- Call helpers from expressions: `let adjusted be normalize_score(score)`.

## User Input and Forms
- Single input: `ask user for "Email" as email`.
- Forms: `form "Signup" as signup:` with typed fields and validation.

## Logging and Observability
- Structured logs: `log info "Starting checkout" with { order_id: order.id }`.
- Use `note` for lightweight markers and `checkpoint` for milestones.

## Deprecation / Legacy Syntax
- Symbolic forms (`let x = ...`, `flow "name":`) are no longer accepted. Use the English `be` assignments and `is` headers everywhere.
