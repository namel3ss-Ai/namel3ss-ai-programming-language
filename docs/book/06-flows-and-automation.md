# Chapter 6 — AI Blocks: Models, System Prompts, and Memory Hooks

- **Models:** `model is "name": provider is "openai_default"`.
- **AI blocks:** `ai is "name": model is "..."; system is "..."; input from <expr>; tools list optional.`
- **Streaming:** `streaming is true` plus stream metadata on steps.
- **Memory hooks:** attach `memory:` to an AI (details in Chapter 7).

Example:
```ai
model is "support-llm":
  provider is "openai_default"

ai is "triage_ai":
  model is "support-llm"
  system is "Classify requests into Billing, Shipping, or Auth."
  input from state.question

flow is "triage":
  step is "answer":
    kind is "ai"
    target is "triage_ai"
    streaming is true
    stream_channel is "chat"
```

Cross-reference: AI/model parsing in `src/namel3ss/parser.py`; runtime routing in `src/namel3ss/ai/registry.py`, `src/namel3ss/ai/router.py`, `src/namel3ss/runtime/context.py`; tests `tests/test_ai_system_prompt.py`, `tests/test_ai_streaming_flag.py`, `tests/test_flow_streaming_runtime.py`; examples `examples/support_bot/support_bot.ai`.
