# Chapter 10 — Tools & Function Calling: Connecting to External APIs

- **Tool declaration:** `tool is "name": kind is "http_json"; method/url/query/headers/body`.
- **Flow call:** `kind is "tool"` step with `input`.
- **AI tool-calling:** Add `tools:` list to an `ai` block; provider executes tools requested by the model.

Example:
```ai
tool is "get_weather":
  kind is "http_json"
  method is "GET"
  url is "https://api.example.com/weather"
  query:
    city: input.city

flow is "weather_now":
  step is "fetch":
    kind is "tool"
    target is "get_weather"
    input:
      city: state.city

ai is "assistant_with_tools":
  model is "support-llm"
  tools:
    - "get_weather"

flow is "chat_with_tools":
  step is "respond":
    kind is "ai"
    target is "assistant_with_tools"
```

Cross-reference: parser tool blocks and AI `tools` list `src/namel3ss/parser.py`; runtime tool registry/execution `src/namel3ss/tools/registry.py`, flow tool steps `src/namel3ss/flows/engine.py`, AI tool loop `src/namel3ss/runtime/context.py`; tests `tests/test_tool_decl_parse.py`, `tests/test_tool_flow_runtime.py`, `tests/test_ai_tool_runtime_loop.py`, `tests/test_ai_tools_list.py`; example `examples/tools_and_ai/tools_and_ai.ai`.
