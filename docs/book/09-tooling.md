# Chapter 9 — Records & CRUD: Building Data-Backed Apps

- **Record:** Typed schema over a frame.
- **Fields:** `type`, `primary_key`, `required`, `default`.
- **CRUD steps:** `db_create`, `db_get`, `db_update`, `db_delete` with `values`, `where`, `by id`, `set`.

Example:
```ai
frame is "projects":
  backend is "memory"
  table is "projects"

record is "Project":
  frame is "projects"
  fields:
    id:
      type is "uuid"
      primary_key is true
      required is true
    owner_id:
      type is "string"
      required is true
    name:
      type is "string"
      required is true
    description:
      type is "text"

flow is "create_project":
  step is "create":
    kind is "db_create"
    record is "Project"
    values:
      id: state.project_id
      owner_id: user.id
      name: state.project_name
      description: state.project_description

flow is "list_projects":
  step is "list":
    kind is "db_get"
    record is "Project"
    where:
      owner_id: user.id

flow is "update_project":
  step is "update":
    kind is "db_update"
    record is "Project"
    by id:
      id: state.project_id
    set:
      name: state.new_name
      description: state.project_description

flow is "delete_project":
  step is "delete":
    kind is "db_delete"
    record is "Project"
    by id:
      id: state.project_id
```

Cross-reference: parser record/CRUD rules `src/namel3ss/parser.py`; runtime frames/records `src/namel3ss/runtime/frames.py`, flow execution `src/namel3ss/flows/engine.py`; tests `tests/test_records_crud.py`, `tests/test_frames_update_delete.py`; example `examples/crud_app/crud_app.ai`.
