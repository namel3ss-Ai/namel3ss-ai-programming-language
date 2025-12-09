# Namel3ss IR overview

The Intermediate Representation (IR) is a normalized, language‑independent view of a Namel3ss program. It is the supported integration surface for analysis tools, migrations, and external runtimes.

## What is in the IR?

- `IRProgram` (top level, includes `version`)
  - `apps`, `pages`, `flows`, `ai_calls`, `agents`, `memories`, `frames`, `records`, `tools`, `vector_stores`, `rulegroups`, and `settings`.
- Flows:
  - `IRFlow` with ordered `IRFlowStep`/`IRFlowLoop` entries.
  - Steps refer to AI calls, agents, tools, frames, records, etc., by name.
- AI calls:
  - `IRAiCall` includes `model_name`/`provider`, system prompt, memory config, and tool bindings.
- Agents:
  - `IRAgent` with goal, plan, and steps.
- Records/frames:
  - Schema information for structured data used by flows and pages.

The IR is designed so tools can resolve references by id/name without needing the original `.ai` source.

## Serialization shape

- The IR serializes to JSON via `dataclasses.asdict(IRProgram)`.
- Important fields:
  - `version`: IR schema version (currently `0.1.0`).
  - `flows`: map of flow name -> `{name, description, steps, error_steps}`.
  - `ai_calls`: map of AI call name -> `{model_name, provider, system_prompt, memory, tools, ...}`.
  - `agents`, `pages`, `memories`, `records`, `tools`, `vector_stores`, etc., follow the same pattern: keyed by name with nested fields.

## Versioning and compatibility

- `IR_VERSION` is defined in `src/namel3ss/ir.py` and stamped on every `IRProgram`.
- Minor version bumps (e.g., 0.1.x) are backwards compatible.
- Breaking IR changes will increment the major/minor version and be documented here.
