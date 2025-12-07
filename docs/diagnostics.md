# Diagnostics

Diagnostics provides structured, code-based feedback produced during parsing,
IR validation, and semantic checks. Each diagnostic has a code, category, and
severity, plus location metadata.

## Categories
- `syntax`
- `lang-spec`
- `semantic`
- `performance`
- `security`

## Severities
- `error`
- `warning`
- `info`

## Codes

| Code     | Category   | Default Severity | Description |
|----------|------------|------------------|-------------|
| N3-0001  | syntax     | error            | Generic syntax/parse error. |
| N3-1010  | lang-spec  | error            | No declarations were found in the source file. |
| N3-1001  | lang-spec  | error            | Missing required field on a block. |
| N3-1002  | lang-spec  | warning          | Unknown field on a block. |
| N3-1003  | lang-spec  | error            | Invalid child block under a parent. |
| N3-1004  | lang-spec  | error            | Duplicate name detected within a unique scope. |
| N3-1005  | lang-spec  | error            | Field has an invalid type or value. |
| N3-2001  | semantic   | error            | Reference to an unknown target (ai/agent/model/memory/etc.). |
| N3-2002  | semantic   | error            | Invalid argument or parameter binding. |
| N3-2101  | semantic   | error            | Variable is not defined when referenced. |
| N3-2102  | semantic   | error            | Variable redeclaration in the same scope. |
| N3-2103  | semantic   | error            | Invalid operator for the provided operand types. |
| N3-2104  | semantic   | error            | Condition did not evaluate to a boolean. |
| N3-2105  | semantic   | error            | Divide-by-zero while evaluating an expression. |
| N3-3200  | semantic   | error            | List builtin is not applicable to the provided type. |
| N3-3201  | semantic   | error            | Filter predicate must evaluate to a boolean. |
| N3-3202  | semantic   | error            | Map expression produced an invalid value. |
| N3-3203  | semantic   | error            | `sum` requires a numeric list. |
| N3-3204  | semantic   | error            | Cannot compare elements for sorting. |
| N3-3205  | semantic   | error            | Index out of bounds. |
| N3-3300  | semantic   | error            | Unknown record field. |
| N3-3301  | semantic   | error            | Invalid record key. |
| N3F-1000 | semantic   | error            | Frame source missing. |
| N3F-1001 | semantic   | error            | Invalid frame configuration. |
| N3F-1002 | semantic   | error            | Unknown column in frame select. |
| N3F-1003 | semantic   | error            | Frame `where` clause must be boolean. |
| N3F-1100 | semantic   | error            | Frame is not loaded or cannot be resolved. |
| N3F-1101 | semantic   | error            | List operation is not applicable to frame value. |
| N3F-1200 | semantic   | error            | Invalid frame expression in aggregate. |
| N3F-1201 | semantic   | error            | Invalid mapping expression for frame. |
| N3M-1000 | semantic   | error            | Macro missing description. |
| N3M-1001 | semantic   | error            | Duplicate macro name. |
| N3M-1002 | semantic   | error            | Invalid macro clause. |
| N3M-1100 | semantic   | error            | Macro not found. |
| N3M-1101 | semantic   | error            | Invalid macro arguments. |
| N3M-1102 | semantic   | error            | AI returned invalid or empty code. |
| N3M-1103 | semantic   | error            | Macro expansion produced no declarations. |
| N3M-1200 | semantic   | error            | AI generation failed for macro. |
| N3M-1201 | semantic   | error            | AI output parse error. |
| N3M-1202 | semantic   | error            | AI output failed lint checks. |
| N3M-1203 | semantic   | error            | Name conflict while merging macro expansion. |
| N3M-1300 | semantic   | error            | Macro expansion too large. |
| N3M-1301 | semantic   | error            | Disallowed syntax in macro expansion. |
| N3M-1302 | semantic   | error            | Recursive macro detected. |
| N3M-5000 | semantic   | error            | Macro `crud_ui` requires a non-empty entity name. |
| N3M-5001 | semantic   | error            | Macro `crud_ui` requires a list of fields. |
| N3M-5002 | semantic   | error            | Macro `crud_ui` produced invalid code. |
| N3M-5003 | semantic   | error            | Macro `crud_ui` produced naming conflicts. |
| N3U-1000 | semantic   | error            | Page must have a name. |
| N3U-1001 | semantic   | error            | Page route must begin with "/". |
| N3U-1002 | semantic   | error            | Duplicate page name. |
| N3U-1003 | semantic   | error            | Duplicate route path. |
| N3U-1004 | semantic   | error            | Page must contain at least one layout element. |
| N3U-1100 | semantic   | error            | Duplicate section name on page. |
| N3U-1200 | semantic   | error            | Form not found for embedding. |
| N3U-1201 | semantic   | error            | Invalid form reference. |
| N3U-1300 | semantic   | error            | Layout element outside of a page or section. |
| N3U-2000 | semantic   | error            | State must be declared inside a page. |
| N3U-2001 | semantic   | error            | Duplicate state name on a page. |
| N3U-2002 | semantic   | error            | Invalid state initializer. |
| N3U-2100 | semantic   | error            | Input must be inside a page or section. |
| N3U-2101 | semantic   | error            | Invalid input type. |
| N3U-2102 | semantic   | error            | Variable name conflicts with an existing declaration. |
| N3U-2200 | semantic   | error            | Button must be inside a page or section. |
| N3U-2201 | semantic   | error            | Button must have an `on click` handler. |
| N3U-2202 | semantic   | error            | Invalid action in click handler. |
| N3U-2300 | semantic   | error            | Conditional must be inside a page or section. |
| N3U-2301 | semantic   | error            | Invalid conditional expression. |
| N3U-2302 | semantic   | error            | Empty or invalid conditional blocks. |
| N3U-3000 | semantic   | error            | Theme must be declared inside settings. |
| N3U-3001 | semantic   | error            | Invalid color literal. |
| N3U-3002 | semantic   | error            | Duplicate theme key. |
| N3U-3100 | semantic   | error            | Invalid color token. |
| N3U-3101 | semantic   | error            | Style directive is in an invalid position. |
| N3U-3200 | semantic   | error            | Invalid alignment keyword. |
| N3U-3201 | semantic   | error            | Alignment not allowed here. |
| N3U-3300 | semantic   | error            | Invalid layout type. |
| N3U-3400 | semantic   | error            | Invalid spacing size. |
| N3U-3401 | semantic   | error            | Spacing directive is outside a UI block. |
| N3U-3500 | semantic   | error            | Component name conflicts with existing declaration. |
| N3U-3501 | semantic   | error            | Component render block is missing. |
| N3U-3502 | semantic   | error            | Invalid component parameter list. |
| N3U-3600 | semantic   | error            | Component not found. |
| N3U-3601 | semantic   | error            | Component argument mismatch. |
| N3U-3602 | semantic   | error            | Unknown component parameter. |
| N3-3400  | semantic   | error            | For-each loop requires a list value. |
| N3-3401  | semantic   | error            | Repeat-up-to requires a numeric count. |
| N3-3402  | semantic   | error            | Invalid loop bounds. |
| N3-4000  | semantic   | error            | String builtin is not applicable to the provided type. |
| N3-4001  | semantic   | error            | `join` requires a list of strings. |
| N3-4002  | semantic   | error            | `split` requires a string separator. |
| N3-4003  | semantic   | error            | `replace` arguments must be strings. |
| N3-4100  | semantic   | error            | Aggregate requires a non-empty numeric list. |
| N3-4101  | semantic   | error            | Invalid precision for `round`. |
| N3-4102  | semantic   | error            | Invalid type for numeric builtin. |
| N3-4200  | semantic   | error            | `any` / `all` requires a list value. |
| N3-4201  | semantic   | error            | Predicate for `any` / `all` must evaluate to a boolean. |
| N3-4300  | semantic   | error            | Invalid pattern in match statement. |
| N3-4301  | semantic   | error            | Match requires a value expression. |
| N3-4302  | semantic   | error            | Pattern type is incompatible with the match value. |
| N3-4305  | semantic   | error            | Builtin does not accept arguments. |
| N3-4400  | semantic   | error            | Success/error pattern used on non-result value. |
| N3-4401  | semantic   | error            | Multiple success patterns unreachable. |
| N3-4402  | semantic   | error            | Multiple error patterns unreachable. |
| N3-4500  | semantic   | error            | Retry requires numeric max attempts. |
| N3-4501  | semantic   | error            | Retry max attempts must be at least 1. |
| N3-4502  | semantic   | error            | Retry used in unsupported context. |
| N3-3001  | performance| warning          | Potentially expensive chain detected (reserved). |
| N3-5000  | semantic   | error            | Ask user label must be a string literal. |
| N3-5001  | semantic   | error            | Invalid validation rule for user input. |
| N3-5010  | semantic   | error            | Form label must be a string literal. |
| N3-5011  | semantic   | error            | Duplicate field identifier in form. |
| N3-5012  | semantic   | error            | Invalid field validation rule. |
| N3-5100  | semantic   | error            | Invalid log level. |
| N3-5101  | semantic   | error            | Log message must be a string literal. |
| N3-5110  | semantic   | error            | Checkpoint label must be a string literal. |
| N3-6000  | semantic   | error            | Unknown helper function. |
| N3-6001  | semantic   | error            | Wrong number of arguments for helper. |
| N3-6002  | semantic   | error            | Return used outside of helper. |
| N3-6003  | semantic   | error            | Duplicate helper identifier. |
| N3-6100  | semantic   | error            | Module not found. |
| N3-6101  | semantic   | error            | Imported symbol not found in module. |
| N3-6102  | semantic   | error            | Cyclic module import detected. |
| N3-6103  | semantic   | error            | Duplicate import identifier. |
| N3-6200  | semantic   | error            | Duplicate environment definition in settings. |
| N3-6201  | semantic   | error            | Duplicate key inside env configuration. |
| N3-6202  | semantic   | error            | Invalid expression in settings. |

See also `docs/language_spec_v3.md` for how these codes relate to specific
language rules and contracts.

## Linting (style & hygiene)

Lint findings are softer, English-style hints that do not block execution. They
carry the `lint` category and typically surface as warnings or infos.

Current rules:

| Code     | Default Severity | Description |
|----------|------------------|-------------|
| N3-L001  | warning          | Variable is declared but never used. |
| N3-L002  | warning          | Helper is defined but never called. |
| N3-L003  | warning          | Duplicate match branch is unreachable. |
| N3-L004  | warning          | Loop bound is very large (heuristic). |
| N3-L005  | warning          | Variable shadows an outer binding. |
| N3-L006  | info             | Prefer `let x be ...` instead of `let x = ...` for English style. |
| N3-L007  | warning          | Legacy syntax detected; prefer modern English-style forms. |

Use `n3 lint` to run only lint rules, or `n3 diagnostics --lint` to include them
alongside hard diagnostics. Lint severities can be tuned or disabled per rule by
adding a `[lint]` section to `namel3ss.toml`, for example:

```toml
[lint]
unused_bindings = "warning"
shadowed_vars   = "off"
prefer_english_let = "info"
```

### CLI examples

```
n3 lint app.ai
n3 diagnostics --lint app.ai
```

Lint warnings do not cause a non-zero exit code unless they escalate to errors
via configuration; diagnostics still fail on errors when using `n3 diagnostics`.

Studio and the VS Code extension surface lint findings alongside diagnostics as
soft warnings, making it easy to spot style issues without blocking execution.
