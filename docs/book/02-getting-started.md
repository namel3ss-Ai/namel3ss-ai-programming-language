# Chapter 2 — Getting Started: A First Namel3ss App

A minimal app with UI, a flow, and an AI call:

```ai
app is "hello-app":
  entry_page is "home"

model is "default-model":
  provider is "openai_default"

ai is "greeter":
  model is "default-model"
  system is "Be a concise greeter."
  input from user_input

flow is "welcome":
  step is "say":
    kind is "ai"
    target is "greeter"

page is "home" at "/":
  section is "hero":
    heading is "Hello Namel3ss"
    text is "Type a greeting and click Run."
    input is "user_input":
      bind is state.user_input
    button is "Run":
      on click:
        do flow "welcome"
    text is "Result:"
    text is step.say.output
```

Run via CLI:
```bash
n3 run welcome --file hello.ai --input "Hello there!"
```
Open in Studio to preview the page, click the button, and watch the flow execute.

Cross-reference: parser (app/page/ai/flow/UI) in `src/namel3ss/parser.py`; runtime flow execution in `src/namel3ss/flows/engine.py`; UI manifest in `src/namel3ss/ui/manifest.py`; tests `tests/test_parser_flow.py`, `tests/test_ui_pages.py`, `tests/test_flow_engine.py`; example seed `examples/getting_started/app.ai`.
