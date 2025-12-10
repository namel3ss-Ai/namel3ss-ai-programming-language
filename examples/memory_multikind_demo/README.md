# Memory Multikind Demo

This demo shows how to mix multiple memory kinds and pipelines inside a single AI:

- `memory profile is "shared_conversation"` defines short-term, episodic, semantic, and profile stores plus their policies: scopes (`per_session`, `per_user`, `shared`), retention windows, `pii_policy`, and an episodic `time_decay` half-life.
- The `travel_planner` AI references that profile, adds recall rules for each kind, and layers inline pipelines so short-term chats are summarised into episodic memory and fresh profile facts are extracted automatically.
- The `plan_trip` flow simply invokes the AI, but you can extend it with tools or additional steps to see the pipelines fire after each response.

Run it with the golden example test harness or wire the AI into a flow in your own app to inspect the episodic/profile stores after each call.

## Inspecting the demo’s memory

- Start the local server with `n3 serve` and open Studio → Memory Inspector. Select the `travel_planner` AI, pick a session, or type a user id to see:
  - the merged memory profile + inline overrides (scopes, retention, pii policy, time_decay),
  - the current short-term/episodic/semantic/profile entries,
  - the recall rules and the last recall snapshot (with per-kind diagnostics).
- From a terminal you can print the same view with:

  ```
  n3 memory-inspect --file memory_multikind_demo.ai --ai travel_planner --session-id demo-session
  ```

  Add `--user-id demo-user` or `--plan-only` depending on what you want to inspect. The CLI output is JSON, so you can diff it inside tests or pipe it into other tooling.
