# Records & Queries

Records give names, types, defaults, and required flags to tabular rows. The English query surface builds on those records so you can filter, sort, and paginate safely.

## Defining records

```
frame is "users":
  backend "memory"
  table "users"

record "User":
  frame is "users"
  fields:
    id:
      type "string"
      primary_key true
    name:
      type "string"
      required true
    is_active:
      type "bool"
      default true
    created_at:
      type "datetime"
      default "now"
```

Defaults are evaluated to concrete values (e.g. `"now"` → a datetime), and required fields are enforced when creating records.

## Creating, updating, deleting

Create:

```
step is "create_user":
  kind is "db_create"
  record "User"
  values:
    id: user.id
    name: user.name
    is_active: user.is_active
```

Update:

```
step is "rename":
  kind is "db_update"
  record "User"
  by id:
    id: user.id
  set:
    name: "New Name"
```

Delete:

```
step is "remove":
  kind is "db_delete"
  record "User"
  by id:
    id: user.id
```

## Querying with `find`

`find <alias> where:` is the canonical query surface. All filters, ordering, and pagination go through one pipeline.

```
step is "list_active":
  find users where:
    is_active is true

  order users by created_at descending, name ascending
  limit users to 20
  offset users by 0
```

- The alias (`users`) is local to the step and maps to the underlying record (`User`).
- WHERE conditions use English operators and must evaluate to booleans.

### WHERE examples

```
status is "active"
age is greater than 18
score is at least 50
country is one of ["BE", "NL"]
deleted_at is null
deleted_at is not null
```

### Ordering

```
order users by status ascending, created_at descending
```

Each field can specify `ascending` or `descending` (ascending is the default).

### Pagination

```
limit users to 20
offset users by 40
```

`limit`/`offset` must be non-negative numbers; offset defaults to 0 when omitted.

### Errors and diagnostics

- Non-boolean WHERE conditions raise a clear error.
- Invalid limit/offset values produce an English error explaining the expectation.
- Sorting by a field that is missing on some rows raises a diagnostic naming the field.

## Design notes

- `find ... where:` replaces `db_get`; everything now flows through a single English-first query pipeline.
- Ordering and pagination are part of the same surface so backends can plug in cleanly later.
- Default handling and required fields are enforced at runtime using the record schema.
- See `examples/records_queries_demo/records_queries_demo.ai` for a runnable demonstration of `find` with ordering and pagination.
