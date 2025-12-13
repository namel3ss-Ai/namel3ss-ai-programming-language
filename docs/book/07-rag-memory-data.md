# Chapter 7 — Memory: Conversation, Long-Term, Episodic, Semantic, and Profiles

- **Kinds:** `short_term` (working memory), `long_term` (durable chat log), `episodic` (important events), `semantic` (knowledge/document snippets), `profile` (structured user facts).
- **Policies:** `scope` (`per_session`, `per_user`, `shared` with per-kind defaults), `retention_days` (positive integers, auto-pruned), `pii_policy` (`none` or `strip-email-ip`), and optional `time_decay` blocks to bias recall toward fresher entries.
- **Pipelines:** `llm_summariser`, `llm_fact_extractor`, and `vectoriser` run immediately after each turn to compress, extract, or enrich data.
- **Recall:** Ordered rules pulling from any combination of kinds using `count`, `top_k`, or `include`.

**Example 1 — Lightweight chat + profile facts**

```ai
ai is "support_ai":
  model is "support-llm"
  system is "Support bot. Use recall and profile facts."
  memory:
    kinds:
      short_term:
        window is 8
        scope is "per_session"
        retention_days is 7

      profile:
        store is "default_memory"
        scope is "per_user"
        pii_policy is "strip-email-ip"
        pipeline is:
          step is "facts":
            type is "llm_fact_extractor"
    recall:
      - source is "short_term"
        count is 6
      - source is "profile"
        include is true
```

**Example 2 — Rich multi-kind memory with decay**

```ai
ai is "travel_planner":
  model is "travel-llm"
  memory:
    kinds:
      short_term:
        scope is "per_session"

      episodic:
        store is "trip_episodes"
        scope is "per_user"
        retention_days is 365
        time_decay:
          half_life_days is 30
        pipeline is:
          step is "summarise_short_term":
            type is "llm_summariser"
            max_tokens is 512
            target_kind is "episodic"

      semantic:
        store is "travel_kb"
        scope is "shared"

      profile:
        store is "user_profiles"
        scope is "per_user"
        pii_policy is "strip-email-ip"

    recall:
      - source is "short_term"
        count is 12
      - source is "episodic"
        top_k is 6
      - source is "semantic"
        top_k is 6
      - source is "profile"
        include is true
```

Cross-reference: parser memory rules `src/namel3ss/parser.py`; runtime memory stores/pipelines `src/namel3ss/memory/*`, integration `src/namel3ss/runtime/context.py`; tests `tests/test_memory_conversation.py`, `tests/test_memory_multikind.py`, `tests/test_memory_retention.py`, `tests/test_memory_inspector_api.py`; example `examples/support_bot/support_bot.ai`.

## Inspecting memory while you build

Once your app is running under `n3 serve`, open Studio and switch to the **Memory Inspector** tab:

- Choose an AI from the dropdown, then either click a recent session or type a user id.
- The left column lists sessions harvested from short-term memory, while the right column shows:
  - the normalized memory plan (per-kind scope, retention, pii_policy, time_decay, and pipelines),
  - the recall rules in the order they will run,
  - the current stored entries for each enabled kind (short-term turns, episodic/semantic items with decay scores, profile facts, and so on),
  - the most recent recall snapshot with diagnostics explaining how many entries came from each kind.
- Everything is read-only and already scrubbed according to the configured `pii_policy`, so you can safely share screenshots when debugging.

Prefer the CLI? Use the same helper with:

```
n3 memory-inspect --file app.ai --ai support_ai --session-id sess-abc
```

Add `--user-id user-123` to focus on per-user scopes or `--plan-only` to print just the config. The JSON mirrors what Studio renders, meaning you can diff memory state in tests or CI.
