# Optimizer

The optimizer watches metrics, traces, failures, and memory usage to propose improvements:
- Model selection, flow parallelism/timeouts
- Prompt tuning hints
- Tool/memory policies (retries, pruning)

Suggestions are persisted, can be applied or rejected, and materialize as runtime overlays without changing DSL source. Optional AI-assisted analysis is available when configured.
