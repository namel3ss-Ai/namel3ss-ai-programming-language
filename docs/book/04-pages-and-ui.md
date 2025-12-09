# Chapter 4 — Variables, State, and Scope

- **State:** `state.foo` persists through a flow run; set via `set state.foo be ...`.
- **User:** `user.id`, `user.email` available after login when auth is configured.
- **Step outputs:** `step.load_user.output.email`.
- **Locals:** `let total be step.fetch.output.count`.
- **Loop vars:** Declared in `for each item in state.items`.
- **Roots:** `state`, `user`, `step`, `input`, `secret`, loop vars, locals. Unknown identifiers raise diagnostics.

Example:
```ai
flow is "calculate":
  step is "sum":
    kind is "set"
    set:
      state.total be state.a + state.b

  step is "store_local":
    let doubled be state.total * 2
    set state.doubled be doubled

  step is "fanout":
    for each item in state.items:
      step is "collect":
        kind is "set"
        set:
          state.collected be (state.collected or []) + [item]
```

Cross-reference: parser expression/scope rules in `src/namel3ss/parser.py`; evaluation in `src/namel3ss/runtime/expressions.py`; tests `tests/test_flow_let.py`, `tests/test_flow_set_state.py`, `tests/test_flow_loops_language.py`, `tests/test_variable_scope.py`.
