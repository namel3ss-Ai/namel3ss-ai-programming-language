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
| N3-L008  | warning  | Naming: prefer `snake_case` for identifiers. |
| N3-L009  | info     | Naming: boolean values should start with `is_`, `has_`, `can_`, or `should_`. |
| N3-L010  | info     | Naming: loop variable should be singular when iterating a plural list. |

Use the lint API (`namel3ss.linting.lint_source` or `lint_module`) to run these rules programmatically. Future versions may add more rules; existing IDs are stable for 1.x.

### Examples

- Snake case: `let user_email be input.email` (instead of `let userEmail be ...`).
- Boolean prefix: `let is_active be status is "active"` (instead of `let active be ...`).
- Plural vs singular loop: `repeat for each user in users:` (loop var `user`, list `users`).
- English assignment: `let total be base plus bonus` and `set state.total be total`.
