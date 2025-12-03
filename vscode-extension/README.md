# Namel3ss VS Code Extension

Features:
- Recognizes `.ai` files and provides syntax highlighting for the Namel3ss DSL.
- Commands:
  - `Namel3ss: Parse current file` (`namel3ss.runParse`)
  - `Namel3ss: Run diagnostics on current file` (`namel3ss.runDiagnostics`)

Install locally:
```
cd vscode-extension
npm install
npm run build
# optional: package with vsce (not included in dev deps)
```

Commands shell out to the `n3` CLI; ensure it is on PATH.
