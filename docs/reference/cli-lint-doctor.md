# `n3 lint` and `n3 doctor`

Use these commands to catch problems before runtime and to verify your environment.

## `n3 lint`

```
n3 lint .                 # lint all .ai files under the current directory
n3 lint path/to/app.ai    # lint a single file
n3 lint . --json          # machine-readable output
n3 lint . --strict        # treat warnings (lang-spec/semantic) as errors
```

Output shows file, line/column, code, message, and hint. Exit code is non-zero when errors are present (or when `--strict` upgrades warnings).

## `n3 doctor`

```
n3 doctor
```

Runs a lightweight health check:
- Prints Namel3ss version and IR version.
- Verifies Python version.
- Warns when no provider API keys are detected.
- Notes whether the golden manifest (`examples/golden_examples.json`) is present.

Exit code is non-zero only when a critical error is detected; warnings are informational so you can address them before deploying.

Use `n3 doctor` after installing the CLI or before CI/deployment to ensure common prerequisites are in place.
