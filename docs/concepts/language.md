# Language

The Namel3ss DSL describes apps, pages, models, ai calls, agents, flows, plugins, memory, datasets, indexes, and UI components. The grammar is stable in V3; runtime features are layered on top without changing syntax or IR semantics.

Pipeline: **lexer → parser → AST → IR → runtime graph**. Diagnostics validate IR contracts before execution.
