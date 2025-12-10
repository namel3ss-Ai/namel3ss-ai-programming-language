# Data & Collections

Data in Namel3ss revolves around three core shapes:

- **Lists** for ordered values.
- **Records** for structured key/value data.
- **Frames** for tabular sources (CSV or in-memory), treated like lists of row-records.

Collection pipelines let you transform these sources in an English style: filter rows, group, aggregate, sort, and slice—all without mutating the original data.

## Lists

Lists are ordered, immutable sequences:

```ai
let xs be [1, 2, 3]
let people be [{ name: "Alice" }, { name: "Bob" }]
```

Common helpers return new lists (never mutate the original):

```ai
let xs be [1, 2, 3]
let ys be append xs with 4          # [1, 2, 3, 4]
let zs be insert 0 at 0 into ys     # [0, 1, 2, 3, 4]
let ws be remove 2 from zs          # [0, 1, 3, 4]
```

Aggregates work on numeric lists:

```ai
let total be sum of xs
let avg be mean of xs
let min_v be minimum of xs
let max_v be maximum of xs
let count be count of xs
```

## Records and safe access

Records are immutable key/value objects:

```ai
let user be { name: "Alice", email: "alice@example.com" }
let { name, email } be user
```

Loop destructuring keeps code readable:

```ai
repeat for each { name, total } in top_customers:
  log info "Customer" with { name: name, total: total }
```

Safe access avoids missing-field crashes:

```ai
let email be get user.email otherwise "unknown"
let has_vat be has key "vat_number" on user
```

Use `get ... otherwise ...` when the field might be absent; direct `record.field` is strict and surfaces a diagnostic with available keys.

## Collection pipelines

Attach a pipeline to a `let` with a trailing colon. Each step refines or reshapes the collection:

```ai
let big_numbers be [1, 5, 10, 20]:
  keep rows where row > 5
  sort rows by row descending
  take first 2
```

A record-focused filter:

```ai
let paid_orders be orders:
  keep rows where row.status is "paid"
  keep rows where row.country is "BE"
  sort rows by row.created_at descending
  take first 100
```

Supported steps (in order of application):

- `keep rows where …` / `drop rows where …`
- `group by …:` with `let` bindings inside
- `sort rows by …` or `sort groups by … [descending]`
- `take first N` / `skip first N`

## Grouping and aggregation

Group pipelines bind `rows` to the rows in each group so you can aggregate:

```ai
let summary be sales:
  group by row.customer_id:
    let total_spent be sum of row.amount
    let orders_count be count of rows
    let avg_order_value be mean of row.amount
  sort groups by total_spent descending
  take first 50
```

Notes:

- `rows` is the list of records for the current group.
- Aggregates expect numeric lists and will raise clear errors on non-numeric data or empty lists (for `mean`/`minimum`/`maximum`).

## Frames as collections

Frames load tabular data and behave like collections of records in pipelines:

```ai
frame is "sales_data":
  source:
    from file "data/sales.csv"
    has headers

let be_customers be sales_data:
  keep rows where row.country is "BE"
  group by row.customer_id:
    let total_spent be sum of row.amount
  sort groups by total_spent descending
```

Pipelines work the same way on frames and plain lists.

## Migrating from the old `all ... from ...`

Legacy constructs like `all row from sales where ...` have been replaced by pipelines. Example:

```
# Before (legacy)
let filtered be all row from sales where row.country is "BE"

# After (pipeline)
let filtered be sales:
  keep rows where row.country is "BE"
```

Use `n3 migrate data-pipelines` to rewrite simple legacy filters automatically. New docs, examples, and snippets only show the pipeline style.
