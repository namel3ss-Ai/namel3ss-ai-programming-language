# 5. Models, AI, and Agents

## Configuring models and providers
- Set `OPENAI_API_KEY` (or the relevant env var) to enable the built-in default provider.
- Or declare providers in `namel3ss.config.json`:
  ```json
  {
    "providers": {
      "openai_default": {
        "type": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "model_default": "gpt-4.1-mini"
      }
    },
    "default": "openai_default"
  }
  ```
- Missing keys surface as `N3P-1801`; unauthorized keys (401/403) surface as `N3P-1802`.

Model binding stays simple:
```ai
model "default":
  provider "openai_default"
```
You can also use Gemini and other supported providers. Streaming and JSON mode are available where implemented.

## AI calls
```ai
ai "summarize":
  model "default"
  # optionally override the provider per call
  provider "openai_default"
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
