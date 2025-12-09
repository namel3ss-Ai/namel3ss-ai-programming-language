# Chapter 5 — Flows: Logic, Conditions, and Error Handling

- **Syntax:** `flow is "name":` with ordered `step` blocks.
- **Kinds:** `ai`, `set`, `db_create/get/update/delete`, `vector_index_frame`, `vector_query`, `tool`, `auth_register/login/logout`, and control constructs.
- **Conditions:** `when <expr>` on a step.
- **Loops:** `for each item in <expr>:` containing nested steps.
- **Errors:** `on error:` with fallback steps.

Example:
```ai
flow is "process_ticket":
  step is "load_user":
    kind is "db_get"
    record is "User"
    where:
      id: user.id

  step is "maybe_assign":
    kind is "set"
    set:
      state.assignee be "support" if step.load_user.output.tier == "premium" else "triage"

  step is "notify":
    kind is "tool"
    target is "notify_slack"
    input:
      message: "New ticket from " + user.id
    when state.assignee == "support"

  on error:
    step is "fallback":
      kind is "set"
      set:
        state.error be "Ticket handling failed."
```

Cross-reference: parser flow/step/when/for/on error in `src/namel3ss/parser.py`; execution in `src/namel3ss/flows/engine.py`; tests `tests/test_flow_engine_v3.py`, `tests/test_flow_step_when.py`, `tests/test_flow_for_each.py`, `tests/test_flow_error_handler.py`, `tests/test_flow_try_catch.py`.
