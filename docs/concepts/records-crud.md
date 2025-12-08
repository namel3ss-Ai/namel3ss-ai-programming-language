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

Fetching by primary key or filters:

```
step is "load":
  kind is "db_get"
  record is "Document"
  by id:
    id: state.document_id

step is "list":
  kind is "db_get"
  record is "Document"
  where:
    project_id: state.project_id
  limit is 20
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

`db_create`/`db_update` coerce and validate fields against the record schema, fill defaults (including `now`), and output the resulting record. `db_get` returns a record or a list depending on whether `by id` or `where` is used. `db_delete` returns an `{ "ok": bool, "deleted": count }` payload.
