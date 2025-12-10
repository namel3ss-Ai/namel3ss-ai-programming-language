# Memory Profiles Demo

This example shows how to declare a reusable memory profile and override it per AI.

- `memory profile is "conversational_short":` defines a shared short-term memory with the friendly defaults (window, scope, recall) injected automatically.
- The `support_agent` AI references that profile with `use memory profile "conversational_short"` and overrides the short-term window to 32 messages in its inline `memory:` block.
- A single flow (`handle_ticket`) calls the AI so you can run `n3 example run memory_profiles_demo` and inspect the merged memory config in Studio.
