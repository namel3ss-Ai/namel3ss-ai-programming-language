# Namel3ss

![Version](https://img.shields.io/badge/version-0.7.0-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)
![Build](https://github.com/namel3ss-Ai/namel3ss-programming-language/actions/workflows/tests.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/namel3ss)

**The AI-native language that reads like intent.**  
One English-ish DSL, one runtime, one Studio: flows, UI, AI, memory, RAG, tools, records/CRUD, auth, and providers in a single `.ai` file.

Install:
```bash
pip install namel3ss
```

---

## What is Namel3ss?
- An English-ish DSL (`is`/`be`) for AI-native apps.
- A runtime that executes flows, AI calls, tools, vector/RAG, CRUD, auth, and UI.
- Studio for preview, flow execution, memory inspection, and provider status.

Cross-reference the source of truth:
- Parser: `src/namel3ss/parser.py`
- Runtime: `src/namel3ss/flows/engine.py`, `src/namel3ss/runtime/context.py`
- UI: `src/namel3ss/ui/manifest.py`
- Memory: `src/namel3ss/memory/*`
- Tools: `src/namel3ss/tools/registry.py`
- Auth: `src/namel3ss/runtime/auth.py`

---

## A glimpse of the language (modern `is`/`be`)
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
    input is "user_input":
      bind is state.user_input
    button is "Run":
      on click:
        do flow "welcome"
    text is step.say.output
```

---

## Quickstart
```bash
pip install namel3ss

n3 parse examples/hello_world/hello_world.ai
n3 run welcome --file examples/hello_world/hello_world.ai --input "Hello there!"

n3 studio   # open the printed URL for UI preview and flow execution
n3 diagnostics --lint examples/hello_world/hello_world.ai
```

Provider config (fast path):
```bash
export OPENAI_API_KEY=sk-...
```
Or `namel3ss.config.json`:
```json
{
  "providers": {
    "openai_default": {
      "type": "openai",
      "api_key_env": "OPENAI_API_KEY",
      "model_default": "gpt-4.1-mini"
    }
  },
  "default": "openai_default"
}
```

---

## Core concepts
- **Flows:** Ordered steps (`ai`, `set`, `db_*`, `vector_*`, `tool`, `auth_*`) with `when`, `for each`, `on error`, `let`, `set state.*`, `step.<name>.output`.
- **AI:** `ai` blocks with `model`, `system`, optional `tools` and `memory`; steps can stream.
- **Memory:** `short_term`, `long_term`, `profile` kinds; `recall`, `scope`, `retention_days`, `pii_policy`.
- **Data & RAG:** `frame`, `vector_store`, `vector_index_frame`, `vector_query`.
- **Records & CRUD:** `record` + `db_create/get/update/delete`.
- **Tools:** `tool` (kind `http_json`), flow `kind is "tool"`, AI tool-calling via `tools: [...]`.
- **Auth:** `auth` config; `auth_register/login/logout`; `user.*` expressions.
- **UI & Navigation:** `page`/`section` with `heading`, `text`, `input`, `textarea`, `button`; `on click` can `do flow` or `navigate to page "/..."`.

---

## Examples
- 🤖 Support Bot (memory + chat): `examples/support_bot/support_bot.ai`
- 🧠 RAG Q&A: `examples/rag_qa/rag_qa.ai`
- 🗂 CRUD + Auth: `examples/crud_app/crud_app.ai`
- 🔧 Tools + AI tool-calling: `examples/tools_and_ai/tools_and_ai.ai`

Run: `n3 example list` then `n3 example run <id>`.

---

## Learn Namel3ss — Book
Each chapter is a focused Markdown file under `docs/book/`:
- Preface: `docs/book/00-preface.md`
- Introduction: `docs/book/01-introduction.md`
- Getting Started: `docs/book/02-getting-started.md`
- Core Concepts: `docs/book/03-language-basics.md`
- Variables & Scope: `docs/book/04-pages-and-ui.md`
- Flows: `docs/book/05-models-and-agents.md`
- AI Blocks: `docs/book/06-flows-and-automation.md`
- Memory: `docs/book/07-rag-memory-data.md`
- Data & RAG: `docs/book/08-deployment.md`
- Records & CRUD: `docs/book/09-tooling.md`
- Tools: `docs/book/10-examples-walkthroughs.md`
- Providers: `docs/book/11-providers.md`
- Auth: `docs/book/11-advanced-topics.md`
- UI & Navigation: `docs/book/12-phase1-capabilities.md`
- Studio: `docs/book/14-studio.md`
- End-to-End App: `docs/book/13-putting-it-together.md`
- Syntax Reference: `docs/book/14-appendix.md`

Prefer the single-file edition? See `docs/book/learn-namel3ss.md`.

---

## Studio
- Preview pages/sections/components with live bindings to `state.*`.
- Execute flows from buttons; inspect step outputs and errors.
- View Memory Inspector (short/long/profile, recall snapshot).
- Check provider status when AI calls fail.

Start Studio:
```bash
n3 studio
```

---

## Community & Contributing
- Issues/Discussions/Roadmap: GitHub
- Contributing: see `CONTRIBUTING`
- License: MIT (`LICENSE`)

Build calm, capable AI-native apps. The DSL stays readable; the runtime and Studio do the heavy lifting.
