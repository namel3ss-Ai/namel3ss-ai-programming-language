# Flows

Flows V3 are runtime graphs (FlowGraph/FlowNode/FlowState) supporting sequential, branching, and parallel execution with join nodes and error boundaries. Shared state passes between steps; triggers (schedule/http/memory/agent-signal) enqueue flow runs as jobs.

Metrics and traces are emitted per node/branch/parallel segment. Flows can run via CLI, HTTP, or Studio.
