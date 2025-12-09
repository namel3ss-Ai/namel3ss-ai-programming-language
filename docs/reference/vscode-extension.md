# VS Code Extension

Install locally:
```
cd vscode-extension
npm install
npm run build
npm test   # validates manifest
```

## Features
- Syntax highlighting for `.ai` files (grammar in `syntaxes/namel3ss.tmLanguage.json`).
- Diagnostics via the language server (LSP) with parser hints and links back to the docs.
- Optional lint-on-save powered by `n3 lint --json` (configurable).
- Hover tooltips for key keywords (`app`, `page`, `flow`, `agent`, `ai`, `memory`, …) with short descriptions and documentation links.
- Commands:
  - `Namel3ss: Restart Language Server` (`namel3ss.restartServer`).
  - `Namel3ss: Lint File` (`namel3ss.runLint`) — runs `n3 lint --json <file>` and surfaces the results in the Problems panel.

Commands rely on the `n3` CLI being on PATH (configurable via `namel3ss.lsp.command`).

## Configuration
- `namel3ss.lsp.command` / `namel3ss.lsp.args`: how the extension launches the LSP (`n3 lsp` by default).
- `namel3ss.lint.onSave`: enable/disable lint-on-save (default: true).
- `namel3ss.lint.command` / `namel3ss.lint.args`: override the command used for linting (defaults to the LSP command with `lint --json`).

Lint diagnostics are shown alongside parser/runtime diagnostics; hints from the parser (e.g., “Did you mean …?”) appear in hover text and the Problems panel.
