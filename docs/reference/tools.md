# Tools & External Integrations (provider-agnostic)

Declare a tool once, wire its inputs, then call it from any flow step.

```ai
tool is "weather_api":
  kind is "http"
  method is "GET"
  url is "https://api.example.com/weather"
  headers:
    Accept: "application/json"
    x-api-key: secret.WEATHER_API_KEY
  query:
    city: input.city
  timeout is 5 seconds
  retry:
    max_attempts is 3
    backoff is "exponential"
    initial_delay is 200 milliseconds
    retry_on_status are [429, 500, 502, 503, 504]
  auth:
    kind is "bearer"
    token is secret.WEATHER_TOKEN
  response_schema:
    type is "object"
    required ["temp_c", "condition"]
    properties:
      temp_c:
        type is "number"
      condition:
        type is "string"
  logging is "debug"
  rate_limit:
    max_calls_per_minute is 60
    burst is 10
  multipart is false
  query_encoding is "repeat"

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

- Supported kinds: `http`/`http_json` for HTTP calls, plus `function`/`local` for non-HTTP adapters.
- `method` must be one of GET/POST/PUT/PATCH/DELETE.
- `url` can be any expression (literal, `config.X`, etc.).
- `query`, `headers`, and `body` blocks accept nested expressions referencing `input.*`, `secret.*`, literals, or other expressions.
- Tool steps use an `input:` object. Every `input.foo` reference inside the tool definition (and placeholders inside `url_template`/`body_template`) becomes a required field; missing values trigger `N3F-965`.
- `timeout is ...` sets the per-attempt timeout (default: 15 seconds). Flows can override per step with `timeout is ...` inside the step block.
- `retry:` block (optional): `max_attempts`, `backoff` (`none`/`constant`/`exponential`), `initial_delay`, `max_delay`, `jitter`, `retry_on_status` (list of HTTP status codes), `retry_on_exceptions` (list of exception names or `true` for network defaults). Unsafe methods are not retried unless `allow_unsafe` is set.
- `auth:` block (optional): `kind` (`bearer`/`basic`/`api_key`). Bearer: `token`; Basic: `username`/`password`; API key: `location` (`header`/`query`), `name`, `value`.
- `response_schema:` block (optional) validates JSON responses. Supported: `type` (`object`/`array`/`string`/`number`/`boolean`), `required [...]` for objects, and `properties:` with per-field `type`. Schema failures set `ok` to `false` and surface a detailed error with a response snippet.
- `logging is "debug" | "info" | "quiet"` toggles request/response logging. `debug` logs method/url/headers and response snippets; `info` logs starts and errors; `quiet` only logs failures. Hooks (`before_tool_call` / `after_tool_call`) let you add custom metrics/logging interceptors.
- The step result is a dict: `{"ok": bool, "status": int | None, "data": <parsed JSON or str>, "headers": {...}, "error"?: str}`.
- Errors include the tool name, method + URL, HTTP status (when present), and a short snippet of the raw response to aid debugging.
- `rate_limit:` block (optional) enables a basic in-process limiter. Fields: `max_calls_per_minute` and/or `max_calls_per_second` (>=1), optional `burst` (>=1). Exceeding the limit returns `ok: false` with a clear rate limit error. Limits are per-tool, per-process (not cluster-wide).
- `multipart is true` switches body encoding to multipart/form-data. Each `body:` field becomes a form part; file-like values (bytes or objects with `.read()`) are sent as files. Without multipart, bodies are JSON (default).
- `query_encoding is "repeat" | "brackets" | "csv"` controls how list query params are encoded. Default: `repeat` (`ids=1&ids=2`). `brackets` => `ids[]=1&ids[]=2`; `csv` => `ids=1,2`.

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
- Providers translate the same tool DSL into their own payloads: OpenAI/compatible (function calling), Gemini (functionDeclarations), Azure OpenAI, or local/dummy providers you stub in tests.
- Provider capabilities are listed in `docs/reference/providers.md`; if a provider does not support tools, the runtime raises a clear error instead of ignoring the `tools:` block.

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
