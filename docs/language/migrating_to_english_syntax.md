# Migrating to English Syntax (Naming Standard v1)

Older Namel3ss code may use symbolic headers and assignments such as:

```ai
flow is "calculate_total":
  step "sum":
    let total = base + bonus
    set state.total = total
```

The current language requires the English forms:

```ai
flow is "calculate_total":
  step is "sum":
    let total be base + bonus
    set state.total be total
```

Use the CLI to migrate automatically:

```bash
# Dry run (default)
n3 migrate naming-standard --path path/to/project --dry-run

# Apply changes with backups (.bak)
n3 migrate naming-standard --path path/to/project --write

# Optionally fix simple camelCase locals
n3 migrate naming-standard --path path/to/project --write --fix-names
```

The migrator rewrites legacy headers (`flow is "name":`, `step "name":`, `page is "name":`, etc.) to `... is "name":` and replaces `let x = ...` / `set state.x = ...` with `let x be ...` / `set state.x be ...`. Arithmetic operators remain unchanged.

Studio also exposes a one-click migration for the current file. Use the **Migrate to English naming** button in the editor toolbar to rewrite the open buffer (optionally fixing camelCase locals). It calls the same migration engine as the CLI and updates your buffer in place.

See also:
- Naming Standard v1: `docs/language/naming_v1.md`
- Variables & Scope walkthrough: `docs/book/variables_and_scope.md`
- Lint rules: `docs/language/lint_rules.md`
