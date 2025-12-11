# Provider Capabilities Matrix

Provider | Chat | Streaming | Tools | Notes
--- | --- | --- | --- | ---
OpenAI | Yes | Yes | Yes | Function calling payload
Azure OpenAI | Yes | Yes | Yes | Same as OpenAI payload
Gemini | Yes | Yes | Yes | `functionDeclarations` for tools
OpenAICompatible / GenericHTTP / LMStudio | Yes | Yes | Yes | OpenAI-compatible function calling
Anthropic | Yes | Yes | No | Tool calling not supported yet (clear error)
Ollama | Yes | Yes | No | Tool calling not supported yet (clear error)
HTTPJson | Yes | No | No | Generic HTTP JSON endpoint; not an LLM tool caller
Dummy | Yes | No | No | Test stub only

Notes:
- The DSL for tools/ai/agent is identical across providers. A provider’s capabilities only affect whether tool calling or streaming is available.
- If you configure tools with a provider that has `No` in the Tools column, the runtime raises a clear error instead of silently ignoring tools.
- Agents call the underlying AI using the same provider capabilities (tools/streaming) as the AI block declares.
