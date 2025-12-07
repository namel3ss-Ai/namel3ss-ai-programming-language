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

## Exercises
1. Add a retry block around an AI step to handle transient failures.
2. Create a match that routes to three different flows.
3. Write a file trigger that filters on `*.txt` and calls a parsing flow.
