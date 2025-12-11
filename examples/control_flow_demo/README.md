# Control Flow Demo

A small, copy-pasteable flow that exercises every Control Flow v1 construct: `if`/`otherwise`, `match`, `repeat for each`, `repeat up to`, flow-level `for each`, `guard`, `retry up to ... with backoff`, `on error`, and the core step kinds (`script`, `tool`).

## Run with the CLI
```bash
n3 example run control_flow_demo
```

## Load in Studio
Open the IDE with:
```
http://localhost:8000/studio?example=control_flow_demo
```

## Files
- `control_flow_demo.ai` — the flow showing guard, match, loops, retry, and on error together.
- `meta.json` — catalog entry for `n3 example list`.

## Result-aware match quick sample

To branch on a result (e.g., a tool call) add success/error clauses:

```ai
match result:
  when success as value:
    set state.payload be value
  when error as err:
    set state.error be err
```

If `result` is not result-like and no `otherwise` is present, the runtime raises a clear error so you can add a fallback.
