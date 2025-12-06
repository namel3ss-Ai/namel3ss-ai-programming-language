# Lint Rules (v1.0)

The lint engine surfaces non-fatal findings to keep code clean and consistent. Each rule reports a rule ID, severity, location, and message.

| Rule ID  | Severity | Description |
|----------|----------|-------------|
| N3-L001  | warning  | Unused variable (including inputs/forms) within scope. |
| N3-L002  | warning  | Helper/function is declared but never called. |
| N3-L003  | warning  | Unreachable match branch (duplicate literal patterns). |
| N3-L004  | warning  | Excessive loop bound (repeat up to > 1000). |
| N3-L005  | warning  | Shadowed variable hides an outer declaration. |
| N3-L006  | warning  | Discouraged syntax: `let x = ...`; prefer `let x be ...`. |

Use the lint API (`namel3ss.linting.lint_source` or `lint_module`) to run these rules programmatically. Future versions may add more rules; existing IDs are stable for 1.x.
