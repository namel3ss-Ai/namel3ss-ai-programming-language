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
