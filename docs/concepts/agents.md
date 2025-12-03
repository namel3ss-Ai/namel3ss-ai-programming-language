# Agents

Agents V3 include planning, retries, reflection/evaluation (deterministic + OpenAI), budget awareness, and teams with voting/aggregation.

Agents run on top of the ModelRouter and ToolRegistry and can be invoked directly (`n3 run-agent`) or inside flows. Tracing/metrics capture steps, evaluations, retries, and votes.
