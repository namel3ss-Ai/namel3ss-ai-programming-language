# Control Flow Walkthrough

This chapter shows how to use the English control-flow constructs in Namel3ss without reading the full spec. Every example uses the modern headers (`flow is "..."`, `step is "..."`, `kind is "..."`) and the script DSL (`let`, `set state`, `do tool`, etc.).

## Overview
- Conditional paths: `if / otherwise if / else`
- Pattern selection: `match / when / otherwise`
- Loops: `repeat for each`, `repeat up to N times`, flow-level `for each item in state.items`
- Precondition guard: `guard condition:`
- Reliability: `retry up to N times [with backoff]`
- Error handling: `on error` block per flow
- Step kinds: `script` (default), `ai`, `agent`, `tool`

See the working example at `examples/control_flow_demo/control_flow_demo.ai`.

## If / Otherwise If / Else
```ai
flow is "eligibility":
  step is "decide":
    let score be input.score

    if score is greater than 80:
      set state.status be "approved"
    otherwise if score is greater than 60:
      set state.status be "review"
    else:
      set state.status be "rejected"
```
Pitfall: conditions must evaluate to boolean. Non-boolean values raise an English diagnostic.

## Match / When / Otherwise
```ai
step is "route_issue":
  match state.issue_type:
    when "billing":
      set state.handler be "billing_agent"
    when "technical":
      set state.handler be "technical_agent"
    otherwise:
      set state.handler be "general_agent"
```
Pitfall: patterns are literal strings/numbers/booleans only; `when` is only valid inside `match`.

## Guard
```ai
step is "checkout":
  guard state.is_authenticated is true:
    set state.error be "not_authenticated"
    set state.status be "blocked"

  set state.status be "ok"
```
Pitfall: the condition must be boolean; when true the guard body is skipped, when false the body runs and execution continues after the guard.

## Loops
Script-level loops:
```ai
repeat for each ticket in state.tickets:
  set state.last_ticket be ticket

repeat up to max_attempts times:
  do tool "ping"
```
Flow-level fan-out:
```ai
for each item in state.items:
  step is "process":
    kind is "tool"
    target is "echo"
    message is item
```
Pitfalls: `repeat for each` expects a list; `repeat up to` expects a non-negative number.

## Retry
```ai
step is "unstable_call":
  retry up to 3 times with backoff:
    do tool "flaky_service"
```
Pitfall: retry counts must be non-negative numbers; after all attempts fail, the error propagates so `on error` can handle it.

## On Error
```ai
flow is "with_fallback":
  step is "primary":
    kind is "tool"
    target is "unstable_tool"

  on error:
    step is "fallback":
      set state.error_handled be true
```
Pitfall: only one `on error` block per flow; it runs after the first failure unless a retry succeeds.

## Step Kinds and Control Flow
Step kinds integrate with all constructs:
- `script` (default) steps run DSL statements including conditions, loops, retry, guard.
- `ai`, `agent`, `tool` steps can be placed inside loops or retry blocks and can trigger `on error` when they fail.
- Unknown or missing targets produce English diagnostics.

## Patterns and Recipes
**Guard + on error**
```ai
step is "checkout":
  guard user_is_authenticated:
    set state.error be "not_authenticated"
    set state.status be "blocked"
    return

  retry up to 3 times:
    do tool "charge_payment"
```

**Match + loop**
```ai
step is "route_tickets":
  repeat for each ticket in state.tickets:
    match ticket.category:
      when "billing":
        do agent "billing_agent"
      when "technical":
        do agent "technical_agent"
      otherwise:
        do agent "general_agent"
```

**Retry around AI/tool**
```ai
step is "summarize_with_retry":
  retry up to 2 times with backoff:
    do ai "summarizer"
```

## Full Example
Open `examples/control_flow_demo/control_flow_demo.ai` for a complete, runnable walkthrough that combines guard, match, loops, retry, on error, and the core step kinds. You can load it in Studio or run it with `n3 example run control_flow_demo`.
