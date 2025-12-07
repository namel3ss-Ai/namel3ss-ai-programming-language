# Appendix: Legacy Syntax & Migration

Legacy colon/symbolic syntax is supported for backwards compatibility, but the canonical language is the modern English-style DSL.

## What legacy looks like
- `let x = 1` instead of `let x be 1`
- Colon-based blocks for pages/flows/agents

## How it works today
- The parser/transformer can read legacy files and produce the canonical AST.
- Lint warnings (e.g., `N3-L007`) flag legacy forms to help you modernize.

## How to migrate
1. Replace `=` with `be` in `let` bindings.
2. Rewrite colon-based blocks into the modern English page/flow structure.
3. Run `n3 lint` to catch remaining legacy patterns.

## Safe to mix, but not recommended
You can mix styles temporarily; keep projects consistent by migrating fully when possible.

## Resources
- Language spec and style guide
- `n3 lint` for gentle reminders
- Examples in this book and under `examples/` show the modern style exclusively.
