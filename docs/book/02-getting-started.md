# 2. Getting Started

## Install the CLI
Requirements: Python 3.11+
```bash
pip install namel3ss
```
For contributing to this repo, use `pip install -e .[dev]` instead.

## First program: Hello World
Create `hello.ai`:
```ai
app "hello":
  entry_page "home"

page "home" at "/":
  section "hero":
    heading "Hello Namel3ss"
    text "You just wrote your first Namel3ss page."
```

Run and inspect:
```bash
n3 parse hello.ai
n3 run hello --file hello.ai
```

## Configure a provider quickly
Set an API key in your shell:
```bash
export OPENAI_API_KEY=sk-...
```
Or add a project config file:
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
If you forget a key, runtime diagnostics surface `N3P-1801` (missing key) instead of cryptic failures.

## Diagnostics and lint
- **Diagnostics**: `n3 diagnostics hello.ai` shows parse/semantic issues.
- **Lint**: `n3 lint hello.ai` warns about style (unused vars, legacy syntax, etc.).
Lint does not block execution by default.

## Studio quick peek
Start backend + Studio shell:
```bash
n3 studio --no-open-browser   # or just n3 studio
```
Then open `http://127.0.0.1:4173/studio` (or the friendly URL printed).

## Exercises
1. Change the heading text and rerun `n3 parse`.
2. Add another section with a second heading.
3. Run `n3 lint hello.ai` and confirm it reports no warnings.
