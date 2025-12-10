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

Defaults are evaluated to concrete values (e.g. `"now"` -> a datetime), and required fields are enforced when creating records.

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

## Constraints, Relationships & Transactions

Constraints & Relationships v1 now layers uniqueness, scoped uniqueness, foreign keys, relationship-aware reads, and transactional execution onto the existing records surface. The parser/runtime enforce these directives in every record step, and `transaction:` blocks wrap multiple steps into a single commit/rollback unit.

### Story: Tenants, Users, Orders

Define tenant-owned users with scoped uniqueness on email and orders that reference those users:

```
record "Tenant":
  field "id" as id:
    type is uuid
    primary key
  field "name" as name:
    type is string
    must be unique

record "User":
  field "id" as id:
    type is uuid
    primary key
  field "tenant_id" as tenant_id:
    type is uuid
    references "Tenant"
    required is true
  field "email" as email:
    type is string
    must be unique within "Tenant"
  field "name" as name:
    type is string
    required is true

record "Order":
  field "id" as id:
    type is uuid
    primary key
  field "tenant_id" as tenant_id:
    type is uuid
    references "Tenant"
    required is true
  field "user_id" as user_id:
    type is uuid
    references "User"
    required is true
  field "user" as user:
    relationship is "User" by user_id
  field "total" as total:
    type is decimal
```

- `must be unique within "Tenant"` means Alice@example.com can appear once per tenant, but two different tenants can each have an Alice.
- `references "User"` ties `user_id` to the User primary key, while the `user` relationship makes it easier to access the related record in flows.

### Relationship-aware reads

```
step is "list_orders_with_users":
  find orders where:
    tenant_id is state.tenant_id
    status is "open"

  with users for each order by user_id
```

- The base `find` pulls open orders for the active tenant.
- `with users for each order by user_id` (forward-looking) enriches each order with its related user so later steps can reference `order.user.email` without writing manual joins.
- Future projections such as `project orders with user as: { order_id: order.id, user_email: user.email }` are also covered in the Constraints & Relationships spec.

See `docs/language/constraints_relationships_v1.md` for the authoritative wording, diagnostics, and rollout plan (C2-C7). This chapter will be updated again when the runtime ships enforcement.

### Story: validations in practice

Field-level validations let you capture business rules directly in the record schema. For example, a catalog might add price bounds, enum statuses, pattern checks, and array limits in one place:

```
record "Product":
  field "id" as id:
    type is uuid
    primary key

  field "price" as price:
    type is float
    must be at least 0
    must be at most 10000

  field "discount_rate" as discount_rate:
    type is decimal
    must be at least 0
    must be at most 1

  field "status" as status:
    type is string
    must be one of ["draft", "active", "archived"]

  field "slug" as slug:
    type is string
    must match pattern "^[a-z0-9-]+$"

  field "tags" as tags:
    type is array
    must have length at most 5
```

Any `db_create`, `db_update`, or bulk helper that violates these rules fails with a precise English error. For example:

```
flow is "seed_invalid_discount":
  step is "create":
    kind is "db_create"
    record "Product"
    values:
      id: "prod-006"
      price: 25
      discount_rate: 2
      status: "draft"
      slug: "too-much"
      tags: ["promo", "featured", "spotlight"]
```

When this runs the runtime rejects the entire step (or transaction block if wrapped) with:

```
I can't save this Product because discount_rate must be at most 1 but got 2.
```

and no records are inserted. The same pipeline powers bulk create/update and `transaction:` blocks, so a single bad row rolls the rest back automatically.

## Design notes

- `find ... where:` replaces `db_get`; everything now flows through a single English-first query pipeline.
- Ordering and pagination are part of the same surface so backends can plug in cleanly later.
- Default handling and required fields are enforced at runtime using the record schema.
- See `examples/records_queries_demo/records_queries_demo.ai` for a runnable demonstration of `find` with ordering and pagination.

### Transactions keep flows atomic

```
flow is "signup_user":
  transaction:
    step is "create_user":
      kind is "db_create"
      record "User"
      values:
        id: state.user_id
        tenant_id: state.tenant_id
        email: state.email
        name: state.name
    step is "welcome_order":
      kind is "db_create"
      record "Order"
      values:
        id: state.order_id
        tenant_id: state.tenant_id
        user_id: state.user_id
        total: 25
  on error:
    step is "log_failure":
      kind is "db_create"
      record "AuditLog"
      values:
        id: state.audit_id
        message: "Signup failed for " + state.email
```

- The transaction snapshots the underlying frames before running the steps. If `create_user` or `welcome_order` hits a uniqueness/FK error, the runtime restores the snapshot so no partial rows linger.
- `on error` runs after the rollback, so the audit log (or notification) can rely on a consistent state.

See `docs/language/constraints_relationships_v1.md` for the authoritative wording, diagnostics, and roadmap plan (C1-C6+). This chapter now reflects the runtime behavior.
