# English-style Conditions

Conditions are indentation-based—no braces, no closing keywords.

## Flow Conditions

```ai
flow "support_flow":
  this flow will:

    step "classify request":
      do ai "classify_issue"

    step "route to handler":
      if result.category is "billing":
        do agent "billing_agent"
      otherwise if result.category is "technical":
        do agent "technical_agent"
      otherwise:
        do agent "general_agent"

    step "maybe escalate":
      when result.priority is "high":
        do agent "escalation_agent"
```

Rules:
- `if <expr>:` starts a chain.
- `otherwise if <expr>:` is the next branch.
- `otherwise:` is the fallback.
- `when <expr>:` is a single-branch check (no else).
- These forms work in flow step bodies and (for agents) directly inside agent definitions.

## Expressions

Supported operators:
- Equality / inequality: `is`, `is not`
- Comparisons: `<`, `>`, `<=`, `>=`
- Logical: `and`, `or`, `not`

Examples:

```ai
if score > 0.8 and user.is_vip:
  do agent "vip_agent"

when not user.is_logged_in:
  do agent "login_helper"
```

Identifiers can be dotted (e.g., `result.category`) and resolve against the flow state.

### Unless

`unless` is a readable inverse: run the block only if the condition is false.

Flow:
```ai
step "check_priority":
  unless result.priority is "low":
    do agent "handle_high_priority"
```

Agent:
```ai
agent "review_agent":
  unless ticket.status is "closed":
    do tool "send_notification"
```

Rules:
- `unless` is equivalent to `if not <expr>`.
- It has no `otherwise` branch.
- Supported anywhere you can place `when`/`if` inside flows or agents.

### Binding Values with `as`

You can capture a value from the condition header and use it inside the block:

Flow:
```ai
step "route":
  if result.category is "billing" as cat:
    do ai "billing_classifier" with message:
      cat
```

Agent:
```ai
agent "triage_agent":
  if user.score > 0.8 as high:
    do tool "send_alert" with message:
      high
```

Rules:
- `as <name>` is optional and comes after the condition expression.
- For comparisons, the bound value is the right-hand side; otherwise it is the evaluated expression result.
- The binding is local to the conditional block and is removed afterward.
- `otherwise` cannot follow `unless`.

### Pattern Matching

You can match shallow structures inside conditions:

```ai
if result matches { category: "billing", priority: high } as details:
  do agent "billing_handler" with details: details
```

Rules:
- Patterns are shallow key/value checks (no nested objects).
- Values can be literals, identifiers, or comparisons.
- `as <name>` binds the entire matched subject when the pattern succeeds.
- Pattern keys cannot be macros or rulegroups.

### Rulegroups (Condition Groups)

Define reusable sets of rules:

```ai
define rulegroup "vip_rules":
  condition "age_ok":
    user.age > 25
  condition "value_ok":
    user.value > 10000
```

Use the whole group (all rules must pass):

```ai
if vip_rules:
  do agent "vip_handler"
```

Or an individual rule:

```ai
when vip_rules.age_ok:
  do tool "age_based_offer"
```

### Runtime Behavior

- Branches are evaluated in order; the first true branch runs, otherwise the fallback (if present).
- `when` runs its body only if the condition is true.
- `unless` runs its body only if the condition is false.
- Pattern matches succeed only if all pairs match.
- Rulegroups evaluate all their rules (for group use) or a single rule (dot form).
- When a branch with a binding is taken, the bound value is available inside that block only and is included in trace metadata.
- Traces include condition evaluations (including macros, patterns, rulegroups) with expression text and result.

## Agent Conditions

You can use the same English `if / otherwise` chains or `when` blocks directly inside an agent:

```ai
agent "support_agent":
  the goal is "Provide helpful answers."

  when user_intent is "billing":
    do tool "lookup_invoice"

  when user_intent is "login":
    do tool "reset_password"

  otherwise:
    do tool "create_ticket"
```

Or with a chain:

```ai
agent "triage_agent":
  if user_intent is "billing":
    do tool "create_billing_ticket"
  otherwise if user_intent is "technical":
    do tool "create_technical_ticket"
  otherwise:
    do tool "create_general_ticket"
```

Semantics match flows: first true branch runs; `when` is a single-branch check; `otherwise` is the fallback.

## Flow Redirection

Inside a flow step or a conditional branch, you can jump to another flow using `go to flow "name"`:

```ai
flow "router":
  step "route":
    if result.category is "billing":
      go to flow "billing_flow"
    otherwise:
      go to flow "fallback_flow"
```

`go to flow` stops the current flow and starts the target flow immediately. When used inside a conditional branch, only the chosen branch's redirect runs. Traces include a `flow.goto` event showing the source and destination flows.

## Condition Macros

You can define reusable condition macros and use them anywhere a normal condition expression is allowed:

```ai
define condition "is_vip" as:
  user.age > 25 and user.value > 10000

flow "router":
  step "route":
    if is_vip:
      do agent "vip_handler"
```

Rules:
- Defined once at the top level: `define condition "name" as: <expression>`.
- Use the macro name as a standalone condition (`if is_vip:`) in flows or agents.
- You can also reference a macro inside pattern values (e.g., `matches { category: is_vip }`), but not as pattern keys.
- Macros cannot be used as binding names (`as name`) and do not introduce side effects.
- Traces include the macro name when it is used as a condition.
