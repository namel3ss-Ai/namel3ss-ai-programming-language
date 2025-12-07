# 9. Tooling: CLI, Studio, VS Code

## CLI essentials
- Parse: `n3 parse file.ai`
- Run: `n3 run <app_or_flow> --file file.ai`
- Diagnostics: `n3 diagnostics --lint file.ai`
- Lint only: `n3 lint file.ai`
- Build: `n3 build <target> [file]`
- Serve backend: `n3 serve --dry-run`

## Studio
- Start via `n3 studio`.
- Preview Mode: interact with UI.
- Inspector Mode: click elements to inspect properties/events.
- AI UI generator and layout editing are available; experimental features are marked via lint warnings if applicable.

## VS Code extension
- Provides syntax highlighting and diagnostics.
- Runs `n3 diagnostics` under the hood; lint findings appear as warnings/infos.

## Exercises
1. Run `n3 diagnostics --lint` on an example file and interpret the output.
2. Use Studio to inspect a page and switch between Preview and Inspector modes.
3. Install the VS Code extension and confirm diagnostics surface in the editor.
