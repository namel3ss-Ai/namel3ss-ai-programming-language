# Chapter 13 — Building UIs & Navigation

- **Components:** `heading`, `text`, `image`, `input`, `textarea`, `button`, layout (rows/columns/cards where present), badges/chat elements.
- **Bindings:** `bind is state.field`.
- **Actions:** In `on click`, use `do flow "name"` (optionally `with` arguments if supported) or navigation: `navigate to page "target"` or `navigate to "/route"`.
- **Conditionals/visibility:** Use `when`/`show` where supported on UI elements.

Example multi-page UI:
```ai
page is "home" at "/":
  section is "hero":
    heading is "Dashboard"
    button is "Go to projects":
      on click:
        navigate to page "projects"

page is "projects" at "/projects":
  section is "list":
    heading is "Projects"
    button is "Create":
      on click:
        do flow "create_project"
    text is "Owner: " + user.id
```

Cross-reference: parser UI/layout/navigation rules `src/namel3ss/parser.py`; UI manifest `src/namel3ss/ui/manifest.py`, runtime `src/namel3ss/ui/runtime.py`; Studio/backend `src/namel3ss/server.py`; tests `tests/test_ui_pages.py`, `tests/test_ui_button_navigate_parse.py`, `tests/test_ui_manifest_navigate.py`, `tests/test_ui_flow_execute.py`; examples `examples/support_bot/support_bot.ai`, `examples/crud_app/crud_app.ai`.
