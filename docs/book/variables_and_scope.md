# Variables & Scope

This chapter shows how to name things, bind values, and read from runtime scopes in Namel3ss using the English-first syntax.

## Locals with `let … be …`

Use `let <name> be <expr>` for mutable locals inside a step or helper. Bare identifiers resolve only to locals or loop variables.

```ai
flow is "welcome_user":
  step is "greet":
    let greeting be "Hello"
    let audience be "world"
    let message be greeting + ", " + audience
```

## Constants with `let constant … be …`

Use `let constant` when a binding must not change. Rebinding a constant raises a clear error.

```ai
    let constant tax_rate be 0.21
    let total_with_tax be subtotal times (1 plus tax_rate)
```

## State with `set state.… be …`

State is explicit and rooted at `state.`.

```ai
    set state.subtotal be total
    set state.total be total_with_tax
```

## Scope roots and bare identifiers

- Bare names → locals and loop variables only.
- Everything else uses explicit roots:
  - `state.<name>` for flow/page state
  - `user.<field>` for user context
  - `step.<name>.output` or step alias for prior step output
  - `input.<field>`, `secret.<NAME>`, `env.<NAME>` for inputs/secrets/env

When the runtime cannot resolve a bare name, it suggests `let <name> be …` or an explicit root.

## Step aliases

Aliases let you refer to step output without repeating the step name:

```ai
  step is "load_user" as user:
    let user_record be { name: "Riley", email: "riley@example.com" }

  step is "send_email":
    let email be user.output.email
```

Aliases are unique per flow and only valid after the aliased step has run.

## Loop variables

Loop variables live only inside the loop body:

```ai
    repeat for each item in items:
      let total be total plus item.price
# Using item after the loop raises an error.
```

## Destructuring basics

Record destructuring:

```ai
    let {name, email as contact_email} be user_record
```

List destructuring (fixed length):

```ai
    let [first_item, second_item] be items
```

## End-to-end example

```ai
flow is "calculate_checkout":
  step is "load_user" as user:
    let user_record be { name: "Riley", email: "riley@example.com" }
    let {name as customer_name, email} be user_record
    set state.customer_name be customer_name
    set state.customer_email be email

  step is "sum_items" as cart:
    let items be [
      { name: "widget", price: 10 },
      { name: "gadget", price: 5 }
    ]
    let constant tax_rate be 0.21
    let subtotal be 0

    repeat for each item in items:
      let subtotal be subtotal plus item.price

    set state.subtotal be subtotal
    set state.total be subtotal times (1 plus tax_rate)

  step is "summary":
    let [first_item, second_item] be state.items
    log info "checkout" with {
      customer: state.customer_name,
      first_item: first_item.name,
      total: state.total
    }
```

See also:

- Naming Standard v1: `docs/language/naming_v1.md`
- English syntax: `docs/language/english_syntax.md`
- Lint rules: `docs/language/lint_rules.md`
- Example: `examples/variables_scope_demo/checkout_scope.ai`
