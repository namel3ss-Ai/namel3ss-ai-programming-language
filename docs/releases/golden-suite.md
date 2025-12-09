# Golden regression suite

The golden suite exercises representative `.ai` examples to catch breaking changes to parsing, IR generation, and lightweight runtime setup.

## What it covers

- Parses and builds IR for curated examples listed in `examples/golden_examples.json`.
- Ensures IR builds without errors and carries the correct IR version.
- Can be extended to light runtime checks without hitting real providers (using dummy providers).

## Adding an example

1. Append the relative `.ai` path to `examples/golden_examples.json`.
2. Keep examples small and provider-free where possible to keep CI fast.
3. Run `python -m pytest tests/test_golden_examples.py -q` to validate.

Any change that breaks a golden example is treated as a breaking change and must go through the deprecation/migration process.
