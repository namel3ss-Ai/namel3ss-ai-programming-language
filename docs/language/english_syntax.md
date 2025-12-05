# English-style Syntax for Namel3ss

Namel3ss now supports a more readable, English-inspired surface syntax. The new style is fully backward compatible with the existing syntax and compiles to the same AST/IR and runtime behavior.

## Complete Example

```ai
remember conversation as "support_history"

use model "support-llm" provided by "openai"

ai "classify_issue":
  when called:
    use model "support-llm"
    input comes from user_input
    describe task as "Classify the user's support request."

agent "support_agent":
  the goal is "Provide a clear, helpful support answer."
  the personality is "patient, concise, calm"

flow "support_flow":
  this flow will:

    first step "classify request":
      do ai "classify_issue"

    then step "respond to user":
      do agent "support_agent"

    finally step "log interaction":
      do tool "echo" with message:
        "User request was processed and logged."

app "support_bot_app":
  starts at page "support_home"
  description "A simple support assistant with memory and classification."

page "support_home":
  found at route "/support"
  titled "Support Assistant"

  section "introduction":
    show text:
      "Welcome! Describe your issue and let the assistant help."

  section "chat":
    show form asking:
      "Describe your issue (login, billing, errors)."
```

## Mapping to Core Concepts

- `remember conversation as "name"` → conversation memory declaration.
- `use model "name" provided by "provider"` → model definition.
- `ai "name": when called: ...` → AI block with `model`, `input`, and optional `description`.
- `agent "name": the goal is "..."; the personality is "..."` → agent definition.
- `flow "name": this flow will: ... do ai/agent/tool ...` → flow with ordered steps; `first/then/finally` are readability sugar.
- `app "name": starts at page "home"` → app entry page + description.
- `page "name": found at route "/"; titled "..."` → page declaration; `show text:` / `show form asking:` map to text/form components.

## Backward Compatibility

The existing syntax (e.g., `memory "m":\n  type "conversation"`) remains fully supported. Formatter output continues to use the original concise style, and both styles can be mixed in the same file.

Use whichever style fits your team; new projects are encouraged to adopt the English-style syntax for readability.

## Conditions (Phase 1)

Flow steps can branch using English-style `if / otherwise` chains or simple `when` checks:

```ai
flow "support_flow":
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

See `docs/language/conditions.md` for the full set of supported operators, macros, rulegroups, patterns, bindings, and flow redirection.

## Conditional Flow Redirection

Inside a flow step (including inside condition branches), you can jump to another flow using plain English:

```ai
flow "main_flow":
  step "route":
    if result.category is "billing":
      go to flow "billing_flow"
    otherwise:
      go to flow "fallback_flow"

flow "billing_flow":
  step "finish":
    do tool "echo"
```

`go to flow "name"` ends the current flow and continues execution in the target flow. When used inside a conditional branch, only the selected branch's redirect runs, and subsequent steps in the current flow are skipped. Traces include a `flow.goto` event showing the source step and destination flow.
