# Exporting IR and migration scaffolds

The CLI provides export commands to help teams inspect IR and scaffold migrations off the Namel3ss runtime.

## Export IR as JSON

```
n3 export ir path/to/app.ai --out app.ir.json
# or print to stdout
n3 export ir path/to/app.ai
```

- Parses the `.ai` file and serializes the `IRProgram` (including `version`) to JSON.
- Useful for offline analysis, integration with other systems, or debugging compiled IR.

## Generate a FastAPI scaffold

```
n3 export fastapi path/to/app.ai --out ./fastapi_scaffold
```

- Builds a minimal FastAPI app with:
  - `main.py` containing a `/flows/{flow_name}` endpoint.
  - `flows.py` with stub async functions for each `IRFlow`.
- Intended as a starting point for teams migrating logic to a custom stack (e.g., FastAPI + LangChain). The generated functions include comments for each IR step.

Notes:
- The scaffold is intentionally lightweight; you will need to implement actual business logic and provider wiring.
- If `fastapi` is not installed, the generated `main.py` includes a small fallback so it can still be imported for inspection/tests.
