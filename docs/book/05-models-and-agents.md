# 5. Models, AI, and Agents

## Configuring models
```ai
model "default":
  provider "openai:gpt-4.1-mini"
```
You can also use Gemini and other supported providers. Streaming and JSON mode are available where implemented (e.g., OpenAI, Gemini).

## AI calls
```ai
ai "summarize":
  model "default"
  input from "user_input"
```
AI steps can run inside flows or agents.

## Agents
```ai
agent "support_agent":
  goal "Provide support answers"
  personality "patient and concise"
```
Agents can call tools, AI, and leverage memory where configured.

## Tooling hints
- Use `n3 diagnostics --lint` to spot style issues.
- For JSON-mode responses, configure provider/model accordingly; invalid JSON raises clear errors.

## Exercises
1. Define a model and an AI call that rewrites user input.
2. Create an agent that routes to a different agent based on a variable.
3. Add a tool step (e.g., `echo`) after an AI step in a flow.
