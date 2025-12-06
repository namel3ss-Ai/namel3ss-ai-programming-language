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
