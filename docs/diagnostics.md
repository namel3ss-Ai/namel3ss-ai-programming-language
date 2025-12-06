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
| N3-3001  | performance| warning          | Potentially expensive chain detected (reserved). |
| N3-5001  | security   | warning          | Insecure configuration detected (reserved). |

See also `docs/language_spec_v3.md` for how these codes relate to specific
language rules and contracts.
