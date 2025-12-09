# Naming Standard v1 (English-First)

Namel3ss reads like English with one obvious way to express common ideas. Naming Standard v1 is the contract for assignments, block headers, scope roots, and identifier styles that the language now enforces.

## Goals
- English-like, easy to read and explain aloud.
- One canonical spelling for assignments and headers (legacy symbolic forms are no longer accepted).
- Clear scoping rules so readers know where data comes from.

## Assignments
- Locals: `let name be <expr>`
- Immutable locals: `let constant name be <expr>` (may not be reassigned)
- State updates: `set state.name be <expr>` (flow/page state)

## Block Headers (English Form)
Use `is` for block names:
- `flow is "checkout":`
- `app is "storefront":`
- `page is "home":`
- `ai is "support_bot":`
- `agent is "planner":`
- `frame is "orders":`
- `memory is "session":`

## Scope Roots
- `state.*` — flow/page state
- `user.*` — user context
- `step.*.output` — prior step outputs (or via a step alias)
- `input.*` — invocation payloads
- `secret.*`, `env.*` — configuration/secrets
- Bare identifiers — locals and loop variables declared with `let` / `let constant` or loop headers

## Naming Conventions
- `lower_snake_case` for variables, parameters, state keys, helpers, and flows.
- Booleans start with `is_`, `has_`, `can_`, or `should_`.
- Lists use plural names (`items`, `users`); loop variables are singular (`item`, `user`).
- Helpers and flows use verb phrases (`calculate_total`, `send_welcome_email`).

Optional but allowed:
- Step aliases: `step is "load_user" as user:` to allow `user.output.email`.
- Destructuring: `let {name, email} be expr`, `let [first_user, second_user] be users`.

## Example
```ai
flow is "calculate_checkout":
  step is "sum_items":
    let items be cart.output.items
    let total be 0

    repeat for each item in items:
      let total be total plus item.price

    set state.subtotal be total

  step is "apply_tax":
    let constant tax_rate be 0.21
    let total_with_tax be state.subtotal times (1 plus tax_rate)
    set state.total be total_with_tax
```

## Why It Matters
This standard makes Namel3ss easier to teach, to read aloud, and to lint. By favoring English constructs and consistent naming, programs become more approachable to non-programmers while still precise enough for tooling and static analysis. See `docs/book/variables_and_scope.md` for a hands-on walkthrough.

## Migrating legacy code
If you have older sources that still use `flow "name":` or `let x = ...`, run the CLI migrator:

```
n3 migrate naming-standard --path your_project --dry-run
n3 migrate naming-standard --path your_project --write
```

Details: `docs/language/migrating_to_english_syntax.md`.
