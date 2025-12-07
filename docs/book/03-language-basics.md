# 3. Language Basics

## Bindings and expressions
- Declare: `let total be base plus bonus`
- Mutate: `set retries to retries + 1`
- Numbers, strings, booleans, lists, records.
- Negative indices and slices follow Python rules:
  ```ai
  let xs be [10, 20, 30, 40]
  let last be xs[-1]
  let tail be xs[-2:]
  ```

## Control flow
- If:
  ```ai
  if score is greater than 0.8:
    do agent "vip"
  ```
- Match:
  ```ai
  match intent:
    when "billing":
      do agent "billing_agent"
    otherwise:
      do agent "fallback_agent"
  ```
- Loops: `repeat for each item in xs:` and `repeat up to 3 times:`

## Builtins and helpers
- String: `trim of text`, `slugify of title`
- List: `length`, `first`, `last`, `sorted form`, `unique`, `sum`
- Numeric: `minimum`, `maximum`, `mean`, `round`, `absolute`
- Time/random: `current timestamp`, `current date`, `random uuid`
- Helpers:
  ```ai
  define helper "double":
    takes x
    returns result
    let result be x times 2
    return result
  ```

## Style guide highlights
- Prefer English assignments (`let x be ...` not `let x = ...`).
- Use descriptive snake_case names.
- Keep match branches ordered; add `otherwise` for clarity.
- Lint rules will warn on legacy or discouraged forms (e.g., N3-L007 for legacy `=`).

## Comments
Use `#` for single-line comments. They can be standalone or inline and are ignored by the compiler/runtime.

```ai
# This is a full-line comment

flow is "chat":  # main chat flow
  step is "answer":
    kind is "ai"  # call the chatbot
    target is "support_bot"
```

## Exercises
1. Write a helper `add_tax` that returns `price * 1.2`.
2. Create a list and slice it with negative indices to extract the last two items.
3. Add a `match` that handles three literal cases and an `otherwise`.
