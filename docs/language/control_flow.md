# Control Flow (Spec v1)

Namel3ss uses English-style control structures for flows and script steps. This page defines the supported forms for version 1 and highlights what is intentionally out of scope for now. All examples use the English surface (`flow is "..."`, `step is "..."`, `let ... be ...`, `set state... be ...`).

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
