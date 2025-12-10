# Constraints & Relationships v1

Constraints & Relationships v1 defines how record definitions express English-first uniqueness, foreign keys, relationships, and field-level validations, and how reads can attach related records. The parser and runtime now implement this surface (C2-C7): every `db_create` / `db_update` / bulk helper enforces these constraints, and transactions wrap multiple steps in a single all-or-nothing unit.

## Goals & Principles

- Use plain English phrases (`must be unique`, `references "User"`, `with users for each order by user_id`).
- Extend the existing record/CRUD surface without introducing SQL fragments or legacy forms.
- Keep `find <alias> where:` as the base query surface; relationship helpers enrich the rows returned by `find`.
- Document runtime expectations (validation, diagnostics) even though enforcement lands in later phases.

## Unique Constraints

### Declaring uniqueness

Uniqueness is declared per field inside a record definition:

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

- `must be unique` means the value must be globally unique across all records of the same type. Primary keys are inherently unique; this directive exposes additional candidate keys (e.g., email).
- `must be unique within "Tenant"` declares scoped uniqueness. The scope name refers to a logical boundary such as tenant, workspace, or region. v1 assumes the scope resolves to an existing field (e.g., `tenant_id`) either by convention or future explicit syntax. The record may contain multiple scoped uniqueness declarations with different scope names.

### Behavior

- Uniqueness is enforced on create and update operations. Any attempt to insert or change a value that collides with an existing record results in a clear English error, for example:
  - `I can't save this User because email "foo@example.com" is already used.`
  - `Each user must have a unique email.`
- Primary keys remain required and unique. Additional uniqueness rules do not replace PK checks; they layer on top of them.
- Scoped uniqueness applies within the declared scope only. Two records in different scopes may share the same value, but duplicates within the same scope are rejected. Runtime adapters will determine the physical constraint strategy (partial indexes, composite keys, etc.).
- Fields participating in uniqueness can still be nullable unless marked `required`. A `null` value bypasses the uniqueness check; once populated, the value must be unique within the applicable scope.

### Scope concept

- Scope names are plain strings. They may reference another record (`"Tenant"`) or a contextual concept ("Organization").
- v1 does not yet mandate how the scope field is selected. Recommended convention: use `<scope>_id` (e.g., `tenant_id`) on the same record. Future phases may add explicit syntax such as `scope field is tenant_id` to disambiguate.

## Foreign Keys

Foreign keys declare that a field references another record's primary key:

```
record "Order":
  field "id" as id:
    type is uuid
    primary key

  field "user_id" as user_id:
    type is uuid
    references "User"
    required is true

  field "tenant_id" as tenant_id:
    type is uuid
    references "Tenant"
```

- `references "User"` indicates `user_id` stores the primary key of `User`. By default the reference targets the primary key field declared on `User`.
- Reference fields follow the same nullability rules as other fields. Combine `references` with `required is true` to enforce mandatory relationships; omit `required` (or set `required is false`) for optional foreign keys that may be `null`.
- Runtime behavior (future phase C3): create/update operations verify that non-null foreign keys point to existing records. Missing targets produce English diagnostics, e.g. `I can't save this Order because user_id does not point to an existing User.`
- Reference validation happens independently of uniqueness. A single field may be both `must be unique` and `references "User"` if the business rule requires unique ownership.

## Field Validation Rules

Fields can declare additional validations beyond `must be present`, uniqueness, and foreign keys. These rules use the same English-first surface and piggyback on the existing constraint pipeline, so single-row, bulk, and transactional writes all evaluate them the same way.

### Additional field types

- `decimal` &mdash; high-precision numeric values (uses full decimal arithmetic internally).
- `array` &mdash; ordered lists of JSON-compatible items. Use `must have length ...` to cap the number of entries.
- `json` &mdash; small structured blobs (objects or arrays) that are stored as-is. Useful for metadata, feature flags, or embedded settings.

### Validation forms

```
field "Price" as price:
  type is "float"
  must be present
  must be at least 0
  must be at most 1000

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

- `must be present` is the plain-English alias for `required`; it is equivalent to `required true`.
- `must be at least …` and `must be at most …` apply to numeric fields (`int`, `float`, `decimal`). The values must be literals, and the runtime rejects rows when the value falls outside the specified range.
- `must have length at least …` / `must have length at most …` apply to strings and arrays. Length is measured in characters for strings and items for arrays.
- `must be one of [ ... ]` declares enum membership. The list must contain at least one literal value, and only string/bool/numeric fields can use it.
- `must match pattern "..."` runs a full regular-expression match (anchored) against string fields. Patterns are validated when the IR is built, so typos are caught at compile time.

All validations skip `null` unless the field is also marked as required, so optional fields can still be cleared explicitly. When validations fail at runtime, the diagnostics are English-first and specific, for example:

- `I can't save this Product because price must be at least 0 but got -10.`
- `I can't save this Product because tags must have length at most 5 items but got 7.`
- `I can't save this Product because status must be one of ["draft", "published", "archived"] but got "deleted".`

The validations run before uniqueness and foreign keys, and they participate in bulk + transaction workflows: a single bad row causes the entire write batch or transaction block to roll back.

## Relationships

Relationships are logical helpers that describe how to traverse from one record to another:

```
record "Order":
  field "user_id" as user_id:
    type is uuid
    references "User"

  field "user" as user:
    relationship is "User" by user_id
```

- `relationship is "User" by user_id` defines a non-persisted field named `user`. It tells the runtime how to fetch the related `User` record using the `user_id` foreign key.
- Relationships can only reference record types; the `by` clause must match a foreign-key field on the same record.
- Nullability follows the foreign key: if `user_id` is `null`, the relationship resolves to `null`. If `user_id` has a value but the target record is missing, v1 treats it as an error (same diagnostic style as FK validation). Future settings may allow silent `null` in reads, but the default is strict.
- Relationship helpers prepare the groundwork for relationship-aware reads and ergonomic object-style access (`order.user.email`). They do not persist additional data.

## Relationship-Aware Reads

`find <alias> where:` remains the canonical way to query records. Relationship helpers run after the base query to enrich each row.

### `with ... for each ... by ...`

```
step is "list_orders_with_users":
  find orders where:
    status is "open"

  with users for each order by user_id
```

- `find orders where:` executes the primary read.
- `with users for each order by user_id` iterates over the result set and loads the related `User` for every `order` using the `user_id` relationship definition. The attached object is exposed in the natural place (`order.user` when referencing the relationship field defined on the record).
- Pluralization (`with users ...`) is descriptive text; it does not imply a collection return. v1 focuses on simple belongs-to relationships. Future phases may add `with line_items for each order` for has-many patterns.
- Execution model: relationship fetches run after the base query, respecting pagination/order. Adapters can choose batched lookups or lazy loading, but the observable behavior is that each order includes its user (or yields an error if the reference is invalid and non-null).
- Missing relationships: if the foreign key is `null`, the attached relationship is `null`. If it is non-null and no record exists, the runtime surfaces an error such as `I can't load the user for order 123 because user_id does not point to an existing User.`

### Optional projections (future-friendly)

Relationship-aware reads can project combined shapes. One possible pattern (documented but optional to implement immediately) is:

```
project orders with user as:
  {
    order_id: order.id,
    total: order.total,
    user_email: user.email
  }
```

This form would run after the relationship helpers and build custom objects. Flag it as a potential extension so downstream implementations can plan for it.

## Interaction with the Query Pipeline

- All relationship helpers hang off the same step as `find`. They do not introduce new step kinds.
- Ordering, limits, and offsets apply before relationships are loaded, ensuring deterministic pagination.
- Attachments are read-only views; they do not automatically persist nested updates. Mutations continue to use `db_create`, `db_update`, and `db_delete` with explicit field assignments.

## Transactions & Consistency

- `transaction:` wraps one or more `step` blocks inside a flow. Every record write (single or bulk) inside the block either commits together or rolls back together.
- When a step inside the transaction fails, the runtime restores the frame snapshot taken before the block started, emits an English diagnostic, and then runs the enclosing `on error` block (if present). This prevents partial inserts or updates from leaking out of the block.
- Nested transactions are not supported in v1; a flow may have multiple transaction blocks, but they cannot be nested. `for each` loops may appear inside a transaction, and each iteration participates in the same transaction state.
- Error style: `This transaction in flow "signup_user" failed and all record changes were rolled back. Reason: email "foo@example.com" is already used.` The reason includes the lower-level constraint failure so authors can fix the data.

## Diagnostics & Error Style

- All new constraints emit English diagnostics matching existing CRUD messaging: "I can't save...", "Each <record> must have...".
- Validation happens on create and update for uniqueness and foreign keys, and during relationship-aware reads for missing related records.
- Error messages should mention both the field and the rule so authors understand how to fix the input.

## Design Notes

- English-first phrasing keeps the DSL approachable for non-SQL builders: `must be unique`, `references "User"`, `with users for each order by user_id` are easier to read than `UNIQUE(email)` or `JOIN users ON ...`.
- The spec layers onto the existing unified CRUD pipeline: record definitions describe schema, CRUD steps enforce it, and relationship helpers plug into `find` without reintroducing legacy `db_get` APIs.
- Database adapters (Postgres, SQLite, future backends) map these declarative rules into physical constraints or transactional checks. The spec does not assume a specific backend.
- This is the authoritative Constraints & Relationships v1 surface. Future work builds on it without renaming directives or reverting to symbolic syntax.

## Future Work

1. **C8 - Cross-flow transactions**: expand transactional guarantees so multiple flows (signup + onboarding) can commit or roll back together.
2. **C9 - Adapter-driven enforcement**: push uniqueness/FK/validation checks down into relational adapters where possible while preserving English diagnostics.
3. **C10 - Studio visibility**: surface transaction boundaries, rollback reasons, validation failures, and relationship joins directly in Studio dashboards/logs.

Constraints & Relationships v1 now covers C1-C7. Future iterations build on this surface instead of introducing alternative syntax.
