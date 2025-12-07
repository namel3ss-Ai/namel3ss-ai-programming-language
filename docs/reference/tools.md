# Tools & External Integrations (HTTP JSON)

Declare external HTTP JSON tools once, then call them from flows. URL templates accept placeholders that are filled from step `args`, and headers can pull values from config or literals.

```ai
tool is "get_weather":
  kind is "http_json"
  method is "GET"
  url_template is "https://api.example.com/weather?city={city}"
  headers:
    x-api-key: config.weather_api_key

flow is "check_weather":
  step is "call_tool":
    kind is "tool"
    target is "get_weather"
    args:
      city: state.city

  step is "store":
    kind is "set"
    target is state.weather
    value is step "call_tool" output
```

Notes & diagnostics (Phase 5A):

- Only `kind is "http_json"` tools are supported in this phase.
- Declaration errors: N3L-960 (kind), N3L-961 (method), N3L-962 (url_template), N3L-964 (unknown tool usage).
- Runtime errors: N3F-963 (HTTP failure), N3F-964 (invalid JSON), N3F-965 (missing arg for a placeholder).
- AI → tool composition arrives in a later phase.

## AI Tool Use (Function Calling)

Enable tools on an `ai` block so the model can call them via function-calling semantics:

```ai
tool is "get_weather":
  kind is "http_json"
  method is "GET"
  url_template is "https://api.example.com/weather?city={city}"

ai is "assistant_with_tools":
  model is "gpt-4.1-mini"
  system is "You are a weather assistant that can call tools."
  tools:
    - "get_weather"

flow is "chat_turn":
  step is "answer":
    kind is "ai"
    target is "assistant_with_tools"
    input:
      question: state.question
```

How it works:

- `tools:` lists declared tools the AI may call.
- Namel3ss sends a tool schema to the provider.
- When the model requests a tool call, Namel3ss executes the tool (HTTP JSON) and feeds the result back.
- The AI then returns the final answer to the flow.

Diagnostics & limits:

- `N3L-970` — unknown tool referenced in `tools:`.
- `N3F-971` — max tool-call depth exceeded.
- Only `http_json` tools are available in this phase.
- Tool use requires a provider that supports function calling (e.g., OpenAI; others depend on your setup).
