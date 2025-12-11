# Chapter 5 — Flows: Logic, Conditions, and Error Handling

- **Syntax:** `flow is "name":` with ordered `step` blocks.
- **Kinds:** `ai`, `set`, `db_create/update/delete`, `vector_index_frame`, `vector_query`, `tool`, `auth_register/login/logout`, and control constructs. Use `find <alias> where:` for record queries.
- **Conditions:** `when <expr>` on a step.
- **Loops:** `for each item in <expr>:` containing nested steps.
- **Errors:** `on error:` with fallback steps.

Example:
```ai
flow is "process_ticket":
  step is "load_user":
    find users where:
      id is user.id

  step is "maybe_assign":
    kind is "set"
    set:
      state.assignee be "support" if step.load_user.output[0].tier == "premium" else "triage"

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

## Multi-agent patterns and evaluation

- Agents can declare a `role` and `can_delegate_to` list to advertise routing targets. Example:
  ```ai
  agent is "router":
    goal is "Send each request to the right specialist."
    role is "router"
    can_delegate_to are ["billing_agent", "tech_agent"]
  ```
- Router/supervisor/debate flows stay in the existing `do agent "..."` surface; helper utilities in `namel3ss.agent.orchestration` wire the common patterns without a new engine.
- Agent evaluation is symmetrical to tool/RAG evals:
  ```ai
  agent evaluation is "support_eval":
    agent is "support_agent"
    dataset_frame is "cases"
    input_mapping:
      question is "user_question"
    expected:
      answer_column is "expected_answer"
      allow_llm_judge is true
      judge_model is "gpt-4o-mini"
    metrics: ["answer_correctness", "latency_seconds", "error_rate"]
  ```
  Run it with `n3 agent-eval --evaluation support_eval --file app.ai`.
