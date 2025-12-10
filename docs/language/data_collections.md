# Data & Collections Reference

## Lists

- Literal: `[1, 2, 3]`, `[ { name: "Alice" }, { name: "Bob" } ]`
- Indexing/slicing: `xs[0]`, `xs[1:3]` (non-negative indices recommended)
- Helpers (pure, return new lists):
  - `append LIST with VALUE`
  - `remove VALUE from LIST` (removes first match; leaves list unchanged if not found)
  - `insert VALUE at INDEX into LIST` (0-based; errors on negative/out-of-bounds)
- Aggregates (numeric lists):
  - `sum of LIST`
  - `mean of LIST` (errors on empty list)
  - `minimum of LIST` / `maximum of LIST` (errors on empty list)
  - `count of LIST` (works on any list)
  - Errors: clear diagnostics for non-numeric items or empty inputs where unsupported.

## Records

- Literal: `{ key: value, nested: { inner: 1 } }`
- Access: `record.field` (strict; surfaces available keys on missing field)
- Destructuring:
  - `let { a, b } be record`
  - `repeat for each { a, b } in records: ...`
- Safe helpers:
  - `get record.field otherwise default`
  - `has key "field" on record`
- Missing fields raise English diagnostics with available keys and typo suggestions.

## Collection pipelines

Attach to a `let` with a trailing colon:

```ai
let result be source:
  keep rows where ...
  drop rows where ...
  group by row.key:
    let metric be sum of row.amount
  sort rows by ...
  sort groups by ... descending
  take first N
  skip first N
```

- `row` is bound for row-level steps; `rows` is bound inside `group by` bodies.
- `group by` bodies support `let` bindings with expressions over `rows`/`row`.
- Sort keys must be comparable; count/take/skip expect non-negative numbers.

## Frames

- Declare a frame:
  ```
  frame is "sales":
    source:
      from file "data/sales.csv"
      has headers
  ```
- Frames behave like list-of-record collections in pipelines (same steps as above).

## Migration note

Legacy `all ... from ...` / `map(...)` syntax is removed. Use pipelines (`keep rows where ...`, `group by ...`) and safe record helpers instead. The CLI helper `n3 migrate data-pipelines` can rewrite simple legacy filters.
