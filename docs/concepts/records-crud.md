# Records & CRUD

Records layer typed models on top of frames so flows can create, read, update, and delete rows through the DSL.

## Declaring a record

```
frame is "documents":
  backend is "default_db"
  table is "documents"

record is "Document":
  frame is "documents"
  fields:
    id:
      type is "uuid"
      primary_key is true
    project_id:
      type is "uuid"
      required is true
    title:
      type is "string"
      required is true
    content:
      type is "text"
    created_at:
      type is "datetime"
      default is "now"
```

`record` attaches typed metadata to the frame/table so CRUD steps know the primary key, required fields, and defaults (including `now` for datetimes).

## CRUD steps in flows

Creating and storing the ID:

```
flow is "create_document":
  step is "create":
    kind is "db_create"
    record is "Document"
    values:
      project_id: state.project_id
      title: state.title
      content: state.content

  step is "store_id":
    kind is "set"
    target is state.document_id
    value is step.create.output.id
```

Querying with English filters, ordering, and pagination:

```
step is "list":
  find documents where:
    project_id is state.project_id

  order documents by created_at descending
  limit documents to 20
```

Updating and deleting:

```
step is "rename":
  kind is "db_update"
  record is "Document"
  by id:
    id: state.document_id
  set:
    title: state.new_title

step is "remove":
  kind is "db_delete"
  record is "Document"
  by id:
    id: state.document_id
```

`db_create`/`db_update` coerce and validate fields against the record schema, fill defaults (including `now`), and output the resulting record. Queries go through `find <alias> where:` so WHERE conditions, ordering, and pagination share the same pipeline. `db_delete` returns an `{ "ok": bool, "deleted": count }` payload.

## Constraints, Relationships & Transactions

Constraints & Relationships v1 extends records with English declarations for uniqueness, foreign keys, relationship-aware reads, and transactional execution. The runtime enforces these rules today: every `db_create` / `db_update` / bulk helper goes through the same pipeline, and a `transaction:` block wraps multiple steps into a single commit/rollback unit.

### Uniqueness

```
record "User":
  field "id" as id:
    type is uuid
    primary key

  field "email" as email:
    type is string
    must be unique

  field "slug" as slug:
    type is string
    must be unique within "Tenant"
```

- `must be unique` ensures the field is globally unique across all Users (beyond the primary key).
- `must be unique within "Tenant"` scopes uniqueness so two tenants can reuse a slug, but duplicates inside the same tenant are rejected.

### Foreign keys & relationships

```
record "Order":
  field "user_id" as user_id:
    type is uuid
    references "User"
    required is true

  field "user" as user:
    relationship is "User" by user_id
```

- `references "User"` declares that `user_id` stores a User primary key (future runtime work will validate it on create/update).
- `relationship is "User" by user_id` provides a friendly way to access the related record as `order.user`.

### Relationship-aware reads

```
step is "list_orders_with_users":
  find orders where:
    status is "open"

  with users for each order by user_id
```

- The `with ... for each ... by ...` helper runs after the base `find` query and attaches each order's related user (eventually exposed via `order.user`).
- Optional projections such as `project orders with user as: { order_id: order.id, user_email: user.email }` are called out in the spec as potential future sugar.

See `docs/language/constraints_relationships_v1.md` for the full specification, diagnostics philosophy, and future milestones (C2-C7).

### Field validations

Records can attach additional validation rules without leaving the English DSL:

```
field "Price" as price:
  type is "float"
  must be at least 0
  must be at most 10000

field "Status" as status:
  type is "string"
  must be one of ["draft", "published", "archived"]

field "Slug" as slug:
  type is "string"
  must match pattern "^[a-z0-9-]+$"

field "Tags" as tags:
  type is "array"
  must have length at most 5
```

- `must be present` is the plain-English alias for `required`.
- Numeric bounds (`must be at least / at most`) apply to `int`, `float`, and `decimal` fields.
- `must have length ...` enforces character counts on strings and item counts on arrays.
- `must be one of [...]` keeps scalar fields inside a known enum.
- `must match pattern "..."` uses regular expressions to keep slugs, emails, etc., in shape.
- Additional field types: `decimal` for precise numerics, `array` for small ordered lists, and `json` for nested metadata blobs.

The runtime reuses the existing constraint pipeline, so single-row writes, `create many ...`, and transactional flows all evaluate validations consistently. Optional fields skip checks when the value is `null`, and errors stay English-first ("I can't save this Product because price must be at least 0 but got -20.").

### Transactions

```
flow is "signup_user":
  transaction:
    step is "create_user":
      kind is "db_create"
      record is "User"
      values:
        id: "user-123"
        email: state.email
    step is "welcome_order":
      kind is "db_create"
      record is "Order"
      values:
        id: "order-123"
        user_id: "user-123"
  on error:
    step is "log_failure":
      kind is "db_create"
      record is "AuditLog"
      values:
        id: "log-123"
        message: "Signup failed"
```

- The transaction block snapshots all record-backed frames before the body runs. If any step fails (duplicate email, missing foreign key, etc.), the runtime restores the snapshot and then runs the `on error` steps.
- Nested transactions are not supported yet; keep each block flat inside the flow or wrap separate sections independently.

See `docs/language/constraints_relationships_v1.md` for the full specification, diagnostics philosophy, and roadmap items (C1-C7+).
