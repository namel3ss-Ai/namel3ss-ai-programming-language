# Versioning and deprecations

Namel3ss follows semantic versioning (`MAJOR.MINOR.PATCH`) for the runtime and a separate version for the IR schema.

## Runtime version

- Defined in `src/namel3ss/version.py` as `__version__`.
- Meaning:
  - Patch (`x.y.z+1`): bug fixes only, no breaking changes.
  - Minor (`x.y+1.0`): additive features, may introduce deprecations, no breaking changes without a deprecation period.
  - Major (`x+1.0.0`): allowed to introduce breaking changes with migration notes.

## IR version

- Defined as `IR_VERSION` in `src/namel3ss/version.py` and stamped onto every `IRProgram.version`.
- Minor updates (e.g., `0.1.x`) are backwards compatible; breaking IR changes bump the minor/major.

## Deprecation policy

- Deprecated features emit a structured warning with a removal target version.
- Environment flag `N3_DEPRECATION_STRICT=true` turns deprecations into errors for teams that want hard enforcement.
- A feature is marked deprecated in one minor release and removed in the next major (or after at least one minor cycle while pre-1.0).

See also:
- `docs/releases/golden-suite.md` for regression coverage.
- `CHANGELOG.md` for release notes.
