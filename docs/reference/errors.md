# Language Errors and Diagnostics

Namel3ss surfaces structured diagnostics with codes so you can quickly understand and fix issues. The most common parser-facing codes are listed below; all other diagnostics continue to use the existing `N3-*` codes.

- `N3L-PARSE-NEWLINE` — Top-level declarations (`app`, `page`, `flow`, `agent`, …) must start on their own line. This is raised when a string is immediately followed by another keyword on the same line (often a missing newline).
- `N3L-PARSE-UNKNOWN-FIELD` — An unexpected field was found inside an `ai` or `agent` block. The diagnostic includes a “Did you mean …?” hint when a close match is detected (for example, `systm` vs `system`).
- `N3L-PARSE-NAVIGATE` — `navigate` is only supported in UI click handlers. Inside flows use `go to page "<name>"` or `go to flow "<name>"` instead.
- `N3L-PARSE-OUTPUT` — `output to` is only supported inside UI event handlers (e.g., button `on click`). Use `output to state.<name>` there, or `let`/`set` and `step.<name>.output` inside flows.

### Reading diagnostics

- **Code**: Stable identifier (e.g., `N3L-PARSE-NEWLINE`).
- **Message**: Human-friendly description of the issue.
- **Hint**: Optional text with a suggested fix (shown in the CLI, LSP, and VS Code diagnostics).
- **Location**: Line/column where the issue was detected.

See `n3 lint --json` for a machine-readable representation suitable for CI and editor integrations. Additional codes can be added over time; any breaking changes will follow the deprecation and release policy described in the release docs.
