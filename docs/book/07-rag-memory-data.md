# Chapter 7 — Memory: Conversation, Long-Term, and Profiles

- **Kinds:** `short_term`, `long_term`, `profile`.
- **Recall:** Ordered rules pulling from each kind.
- **Pipelines:** `llm_summarizer`, `llm_fact_extractor` steps for compaction/facts.
- **Policy:** `scope` (`per_session`, `per_user`, `shared`), `retention_days`, `pii_policy`.

Example:
```ai
memory is "support_memory":
  type is "conversation"

ai is "support_ai":
  model is "support-llm"
  system is "Support bot. Use recall and profile facts."
  memory:
    kinds:
      short_term:
        window is 8
      long_term:
        store is "default_memory"
        scope is "per_user"
        retention_days is 30
        pii_policy is "strip-email"
        pipeline:
          - step is "summarize"
            type is "llm_summarizer"
            max_tokens is 256
      profile:
        store is "default_memory"
        extract_facts is true
        pipeline:
          - step is "facts"
            type is "llm_fact_extractor"
    recall:
      - source is "short_term"
        count is 6
      - source is "long_term"
        top_k is 3
      - source is "profile"
        include is true
```

Cross-reference: parser memory rules `src/namel3ss/parser.py`; runtime memory stores/pipelines `src/namel3ss/memory/*`, integration `src/namel3ss/runtime/context.py`; tests `tests/test_memory_conversation.py`, `tests/test_memory_multikind.py`, `tests/test_memory_retention.py`, `tests/test_memory_inspector_api.py`; example `examples/support_bot/support_bot.ai`.
