# 11. Advanced Topics

## Plugins and extension points
- Plugins live under `plugins/` with `plugin.toml` manifests.
- Use the registry to load custom behaviors; keep within the stable API surface.

## Optimizer
- Provides evaluations and suggestions; managed via CLI/Studio panels.
- Suggestions require explicit accept/reject decisions.

## Experimental features
- Some advanced chat/UI/memory patterns may be marked experimental.
- Lint can warn with experimental-feature messages; treat these as caution signals.
- Behavior may change—consult release notes and diagnostics.

## Future-facing notes
- Keep an eye on release notes (`CHANGELOG.md`) for new capabilities.
- When in doubt, trust the canonical language spec and lint/diagnostics for the source of truth.

## Exercises
1. Explore `plugins/` and identify where manifests live.
2. Add a harmless log statement to a flow and observe it in traces.
3. Turn on lint and note any experimental warnings in your project.
