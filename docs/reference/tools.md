# Tools & External Integrations (HTTP JSON)

Declare a tool once, wire its inputs, then call it from any flow step.

```ai
tool is "weather_api":
  kind is "http_json"
  method is "GET"
  url is "https://api.example.com/weather"
  headers:
    Accept: "application/json"
    x-api-key: secret.WEATHER_API_KEY
  query:
    city: input.city

flow is "get_city_weather":
  step is "fetch":
    kind is "tool"
    tool is "weather_api"
    input:
      city: state.selected_city

  step is "persist":
    kind is "set"
    target is state.weather
    value is step.fetch.output.data
```

Key details:

- Supported kinds: `http_json`.
- `method` must be one of GET/POST/PUT/PATCH/DELETE.
- `url` can be any expression (literal, `config.X`, etc.).
- `query`, `headers`, and `body` blocks accept nested expressions referencing `input.*`, `secret.*`, literals, or other expressions.
- Tool steps use an `input:` object. Every `input.foo` reference inside the tool definition becomes a required field; missing values trigger `N3F-965`.
- The step result is a dict: `{"ok": bool, "status": int | None, "data": <parsed JSON or str>, "headers": {...}, "error"?: str}`.

Diagnostics:

- `N3L-960`: missing/invalid `kind`.
- `N3L-961`: missing/invalid `method`.
- `N3L-962`: URL not provided.
- `N3L-1400`: flow references a tool name that was never declared.
- `N3F-963`: HTTP/network failure.
- `N3F-965`: required input missing or URL/body/query interpolation failed.

### AI Function Calling

Enable AI-driven tool use by listing tools on an `ai` block; Namel3ss automatically builds JSON schemas from the tool definition (based on the `input.*` references).

```ai
ai is "support_bot":
  model is "gpt-4.1-mini"
  system is "You are a helpful support assistant."
  tools:
    - "weather_api"
    - tool is "create_ticket"
      as is "open_ticket"
```

Rules & diagnostics:

- Each entry must reference a declared tool (or built-in). Missing entries raise `N3L-1410`.
- Use `as is "alias"` to expose a friendlier name to the model without renaming the underlying tool.
- Exposed names must be unique within the AI (`N3L-1411` if duplicated).
- If the model ever asks for an alias that does not map to a declared tool, the runtime raises `N3F-972`.

When the AI step runs (non-streaming mode):

1. Messages are built from system prompt + memory + user input.
2. Provider `chat_with_tools` is called with the declared tool schemas.
3. If the model returns tool calls, the runtime executes each tool via the registry, appends the JSON results as `tool` messages, and makes a second provider call (`tool_choice="none"`) to obtain the final natural-language reply.
4. The final response text is returned to the flow, and conversation memory is persisted as usual.

Streaming AI steps do not support tool calling yet. If a streaming step references tools (and `tools is "none"` is not set) the engine raises `N3F-975`.

### Per-step tool mode

Flows can opt a specific AI step out of tool calling even if the AI declares tools:

```ai
step is "answer":
  kind is "ai"
  target is "support_bot"
  tools is "none"   # or "auto" (default)
```

- `tools is "auto"` (default) enables tools when the AI lists them.
- `tools is "none"` forces a plain chat call (`generate`) even if the AI has tools.

### Summary of diagnostics

- `N3L-1410`: AI references a tool that is not declared.
- `N3L-1411`: duplicate exposed name inside an AI `tools:` block.
- `N3F-972`: provider requested a tool alias that does not map to any registered tool.
- `N3F-975`: streaming AI step attempted to use tools.
