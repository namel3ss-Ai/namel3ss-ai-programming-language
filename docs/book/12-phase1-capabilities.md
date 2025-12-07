# Phase 1 — Core Flow & AI Semantics

Phase 1 brings Namel3ss from simple flows to a programmable, AI-native runtime. The constructs below work together in a single, predictable execution model.

## What’s included
- **system** prompts in `ai` (and agent) blocks
- **let** locals with `=` or `be`
- **set state.<field>** with `=` or `be`
- **if / else** conditionals
- **try / catch** error handling
- **for each** loops

## Execution model
- Flows run **top-down**.
- `let` introduces locals; they must be defined before use.
- `set state.<field>` mutates the flow-scoped state dictionary.
- `if` branches evaluate conditions at runtime; `else` is optional.
- `for each` evaluates its iterable once, then runs the body per element in order.
- `try / catch` intercepts errors; the catch identifier holds an error object with `kind` and `message`.
- AI calls include the system prompt as a system-role message when provided.

## Integrated example

```ai
ai "support_bot":
  model "gpt-4.1-mini"
  system "You are a helpful support assistant."

flow "handle_tickets":
  set state.handled_count = 0
  set state.errors = []

  for each ticket in state.tickets:
    try:
      step "answer":
        kind "ai"
        target "support_bot"

      let response be step "answer" output

      if response.urgent:
        set state.last_urgent be ticket
      else:
        set state.last_regular be ticket

      set state.handled_count be state.handled_count + 1
    catch err:
      set state.last_error be err.message

  if state.handled_count > 0:
    set state.status be "ok"
  else:
    set state.status be "empty"
```

This flow exercises every Phase 1 construct: system prompt, locals, state mutation, conditionals, loops, and error handling.
