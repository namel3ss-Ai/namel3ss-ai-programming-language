# 6. Flows and Automation

## Defining flows
```ai
flow "process_ticket":
  description "Classify and respond."
  step "classify":
    kind "ai"
    target "classify_issue"
  step "respond":
    kind "agent"
    target "support_agent"
```

## Control flow
- `match` inside flows for branching.
- `retry up to 3 times:` for unstable steps.
- Loops: `repeat for each item in xs:` to iterate lists.
- Conditional steps with `when` guards:
  ```ai
  flow is "register_user":
    step is "approve":
      when is state.age >= 18
      kind is "set"
      target is state.status
      value is "approved"

    step is "reject":
      when is state.age < 18
      kind is "set"
      target is state.status
      value is "rejected"
  ```
  If `when` evaluates to false, the step is skipped. Combine opposing conditions to model simple if/else without extra syntax.
- Error handling with `on error`:
  ```ai
  flow is "answer_user":
    step is "call_ai":
      kind is "ai"
      target is "support_bot"
      input:
        question: state.question

    on error:
      step is "fallback":
        kind is "set"
        target is state.answer
        value is "Sorry, something went wrong. Please try again later."
  ```
  When a step fails, normal execution stops and the `on error` steps run. Use `error.message` inside the handler to inspect what went wrong.

## Triggers
- Schedule, HTTP, agent-signal, and file triggers are supported.
- File trigger example:
  ```ai
  trigger "import_new_files":
    kind "file"
    path "uploads/"
    pattern "*.csv"
    flow "process_csv_file"
  ```

## Logging & observability
- `log info "message" with { key: value }`
- `note "Message"` and `checkpoint "label"` for trace navigation.

## Tools & external HTTP APIs

Declare tools once, then call them from flows. HTTP JSON tools accept a URL template with placeholders, optional headers, and an HTTP method.

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

Notes and diagnostics:

- Only `kind is "http_json"` tools are supported in this phase.
- Tool declaration errors: N3L-960 (kind), N3L-961 (method), N3L-962 (url_template), N3L-964 (unknown tool in a flow).
- Runtime errors: N3F-963 (HTTP failure), N3F-964 (invalid JSON), N3F-965 (missing arg for a placeholder).
- AI-to-tool composition arrives in a later phase.

## Exercises
1. Add a retry block around an AI step to handle transient failures.
2. Create a match that routes to three different flows.
3. Write a file trigger that filters on `*.txt` and calls a parsing flow.
