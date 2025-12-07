# Namel3ss Language Style Guide

This guide captures the preferred English-first style for writing Namel3ss programs. The lint rules reinforce these guidelines; following them keeps code readable and consistent.

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
- Symbolic `=` in `let` is allowed for backwards compatibility but discouraged; prefer `be`.
- Any future breaking changes will be announced with lint warnings first; existing syntax remains supported in 1.x.
