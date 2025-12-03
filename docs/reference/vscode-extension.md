# VS Code Extension

Install locally:
```
cd vscode-extension
npm install
npm run build
npm test   # validates manifest
```

Features:
- Syntax highlighting for `.ai` files (grammar in `syntaxes/namel3ss.tmLanguage.json`).
- Commands:
  - `Namel3ss: Parse current file` (`namel3ss.runParse`) → runs `n3 parse <file>`.
  - `Namel3ss: Run diagnostics on current file` (`namel3ss.runDiagnostics`) → runs `n3 diagnostics --file <file>`.

Commands rely on the `n3` CLI being on PATH.
