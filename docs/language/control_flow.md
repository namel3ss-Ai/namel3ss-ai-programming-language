# Control Flow (Spec v1)

Namel3ss uses English-style control structures for flows and script steps. This page defines the supported forms for version 1 and highlights what is intentionally out of scope for now. All examples use the English surface (`flow is "..."`, `step is "..."`, `let ... be ...`, `set state... be ...`).

For a full working sample, see `examples/control_flow_demo/control_flow_demo.ai`.

## If / Otherwise If / Else

Canonical form:

```ai
flow is "eligibility":
  step is "check":
    let score be input.score

    if score is greater than 80:
      set state.status be "approved"
    otherwise if score is greater than 60:
      set state.status be "review"
    else:
      set state.status be "rejected"
```

Rules:
- Conditions must evaluate to a boolean.
- Comparisons allow symbols (`>`, `<`, `==`, `!=`, `>=`, `<=`) and English phrases (`is greater than`, `is less than`, `is at least`, `is at most`).
- Logical operators: `and`, `or`, `not`.
- Ternary / inline expressions (e.g., `value if cond else other`) are **not supported** in v1.

## Match / When / Otherwise

Canonical form:

```ai
flow is "router":
  step is "route":
    match state.intent:
      when "billing":
        set state.route be "billing_flow"
      when "support":
        set state.route be "support_flow"
      otherwise:
        set state.route be "fallback_flow"
```

Rules:
- Patterns: literal strings, numbers, or booleans.
- First matching `when` wins; `otherwise` is optional and used as a fallback.
- `when` is only valid inside a `match` block in v1. Use `if` for standalone conditions.
- Advanced patterns (e.g., `when score > 90`, `when error as err`) are **future work**, not part of v1.

## Loops

Script-level loops:

```ai
repeat for each item in items:
  let doubled be item * 2

repeat up to 3 times:
  do tool "unstable_call"
```

Flow-level loops:

```ai
flow is "process_items":
  step is "init":
    set state.items be [1, 2, 3]

  for each item in state.items:
    step is "process":
      set state.last be item
```

Rules:
- Loop variables exist only inside the loop body.
- `repeat for each` expects a list/iterable; non-list values yield a runtime error.
- `repeat up to N times` expects a non-negative number `N` (literal or variable).
- Nested loops are allowed; inner loop variables do not leak outside their loop.
- If the iterable is `None`, the loop runs zero times.
- Failures inside a loop behave like any other step failure: the loop stops, and an `on error` handler (if present) runs before the flow proceeds.

## Guard

`guard` expresses a precondition: when the condition is false, the guard body runs; when true, the guard body is skipped.

```ai
step is "checkout":
  guard user is present:
    set state.error be "not_authenticated"
    # optionally stop/redirect here

  set state.status be "ok"
```

Rules:
- `guard CONDITION:` evaluates the condition once.
- If the condition is true, the body is skipped and execution continues after the guard.
- If the condition is false, the body runs, then execution continues after the guard.
- Conditions must evaluate to boolean values (same rules/diagnostics as `if`). Non-boolean conditions raise: `This guard condition did not evaluate to a boolean value. I got <value> instead. Make sure the condition returns true or false.`
- Guards are valid anywhere statements are allowed (script steps, inside loops, inside retry blocks).

## Step kinds

Steps declare what they do with `kind is "..."`:
- **script** (default when omitted for steps with a script body): runs DSL logic (let/set, if/match, loops, retry, logging). External calls only happen if you make them inside the script.
- **ai:** calls a named AI model. Fails if `target` is missing or the model name is unknown. Output is stored on `step.<name>.output` (and aliases).
- **agent:** delegates to an agent by name. Fails if `target` is missing or unknown. Output is stored on `step.<name>.output`.
- **tool:** calls a registered tool by name. Fails if `target` is missing or the tool is unknown. If no args are provided, the last output is passed as the default payload.

Notes:
- There is no `kind is "set"`; script is the default.
- Unknown kinds produce an English error listing the supported built-ins (`script`, `ai`, `agent`, `tool`). Extension kinds arrive via plugins, not ad-hoc strings.

## Retry

Canonical forms:

```ai
retry up to 3 times:
  do tool "echo"

retry up to max_attempts times with backoff:
  do tool "call_api"
```

Rules:
- Runs the block up to `N` times until it succeeds or attempts are exhausted.
- `N` may be a literal or a variable.
- `with backoff` applies the configured backoff policy (see runtime defaults).
- `retry up to` expects a non-negative number of attempts; `0` skips the block. After all attempts fail, the error propagates so an `on error` handler can catch it.

## On Error

Attach error handling to a flow to run if any step fails:

```ai
flow is "with_fallback":
  step is "primary":
    kind is "tool"
    target is "unstable_tool"

  on error:
    step is "fallback":
      set state.error_handled be true
```

Rules:
- `on error` belongs to the flow; it contains one or more steps to run when the flow encounters an error.
- Inside `on error`, you can use the same constructs as in normal steps (let/set, conditions, etc.).
- Only one `on error` block is allowed per flow.

## Step Kinds

Core kinds in v1:
- `script` (default if `kind` is omitted): allows let/set, if/match, loops, retry, logging, etc.
- `ai`: calls a model/provider.
- `agent`: runs an agent.
- `tool`: invokes a tool.

Notes:
- `kind is "script"` is optional; script is the default.
- `kind is "set"` is not a distinct kind in v1.
- DB/vector/auth/streaming extensions are documented separately.

## Not Supported in v1

- Ternary / inline conditional expressions.
- Standalone `when` (outside of `match`).
- Advanced match patterns (`when expr > 10`, `when error as err`, destructuring in match).
- Special step kinds beyond `script`, `ai`, `agent`, `tool`.
- Rich retry conditions (e.g., retry while ...) beyond the basic `retry up to N [with backoff]`.

## Future Directions

These are candidates for later phases, not part of v1:
- Advanced match patterns (guards, bindings, destructuring).
- Conditional retries (retry while condition holds).
- Early-exit/guard helpers.
- Tighter integration with DB/vector/auth control structures.
