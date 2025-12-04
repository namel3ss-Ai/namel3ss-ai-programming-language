# Namel3ss VS Code Extension

Features:
- Recognizes `.ai` files and provides syntax highlighting for the Namel3ss DSL.
- Starts the built-in Namel3ss language server (`n3 lsp`) to provide diagnostics and formatting.
- Command: `Namel3ss: Restart Language Server` (`namel3ss.restartServer`).

Install locally:
```
cd vscode-extension
npm install
npm run build
# optional: package with vsce (not included in dev deps)
```

The extension launches `n3 lsp`; ensure the `n3` CLI is on your PATH or configure `namel3ss.lsp.command`/`namel3ss.lsp.args` in settings.
