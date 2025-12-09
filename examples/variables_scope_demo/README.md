# Variables & Scope Demo

This example flow highlights the English-first Naming Standard:

- English headers: `flow is ...`, `step is ...`.
- Locals and constants: `let ... be ...`, `let constant ... be ...`.
- State: `set state.<name> be ...`.
- Step alias: `step is "load_user" as user:` then `user.output.email`.
- Loop scoping: loop variable `item` is only inside `repeat for each item in cart.output:`.
- Destructuring: record (`let {name, email} be user_record`) and list (`let [first_item, second_item] be state.items`).

Run this with the Namel3ss CLI to see the resolved state, or open it alongside the walkthrough in `docs/book/variables_and_scope.md`.
