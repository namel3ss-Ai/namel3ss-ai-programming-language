# Variables & Scope

Namel3ss expressions resolve variables by a clear scope model:

- `state.<name>` — mutable flow/page state.
- `user.<field>` — current authenticated user (or `None`/`False` fields when anonymous).
- `step.<name>.output...` — outputs of **previously defined** steps in the same flow.
- `input.<field>` — inputs provided to tools, pipelines, or steps that accept input blocks.
- `secret.<NAME>` — secrets/config values.
- `env.*` / `config.*` — environment or configuration roots (when configured).
- Locals declared with `let` — referenced as bare identifiers (e.g., `foo`).
- Loop variables introduced by `for each` — only valid inside that loop body.

Rules:

- Use the correct root; bare identifiers are only for locals/loop vars.
- Referencing a step output before the step is defined is invalid.
- Loop variables cannot be used outside their loop.
- Unknown variables are compile-time errors (N3L-1700).

Examples:

```
value is state.total               # ok
owner is user.id                   # ok
email is step.load_user.output.email   # ok only if load_user is defined earlier
foo                                # ok only if declared with `let foo is ...`
item                               # ok inside the loop that declared item
```

Invalid patterns:

- `value is foo` (no local `foo`) → N3L-1700
- `value is step.next.output.id` when `next` is later in the flow → N3L-1701
- `value is step.missing.output.id` when step doesn’t exist → N3L-1702
- `value is item` outside its loop → N3L-1703
