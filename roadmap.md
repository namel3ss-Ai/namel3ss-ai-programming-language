# Namel3ss Roadmap

Namel3ss is built on a simple belief:  
AI-native software deserves a language designed for it.  
This roadmap outlines how Namel3ss grows into the most expressive, safe, and empowering AI-native development platform in the world.

---

## Wave 1 — Strengthen the Core
### Language & Runtime Stability
- Finalize the canonical AST and the legacy-to-modern transformer.
- Define stable semantics for pages, flows, agents, datasets, and UI components.
- Complete support for chat, memory, and advanced UI constructs.
- Ensure every shipped example runs cleanly end-to-end.
- Improve error messages, diagnostics, and linting for clarity and trust.

### Developer Experience
- Strengthen the n3 CLI with clear commands for creating, checking, running, and building apps.
- Improve Studio so Code, Inspector, and Preview flows never break or drift.
- Enhance the AI UI generator for robust layout creation.
- Add a polished 10-minute tutorial app as the canonical starting point.

### Foundational Safety
- Add lint rules for insecure or ambiguous patterns.
- Provide safer defaults for endpoints, model calls, and flow execution.
- Introduce runtime constraints for timeouts, retries, and maximum model usage.

---

## Wave 2 — Build AI-Native Power
### Multi-Agent Orchestration
- First-class multi-agent workflows with roles, shared memory, and communication channels.
- Built-in patterns for planner–worker, router–worker, critic–editor, and supervised agents.

### AI-Native Studio
- Deep AI assistance: explain flows and pages, harden agents and add guardrails.
- Suggest tests, observability, and refactoring.
- Blueprints for entire app categories such as support bots, RAG explorers, dashboards, and automation workflows.

### Security & Guardrails
- AI security linting for prompt injection and unsafe model usage.
- Guardrails for external tools, HTTP calls, and untrusted inputs.
- Secure-by-default scaffolding for public endpoints and agent actions.

### Observability & Evaluation
- Add a Run Explorer for inspecting flow lifecycles, costs, and model interactions.
- Build an evaluation harness for regression testing across agents, flows, and model outputs.
- Introduce checkpoints, timelines, and structured logs for debugging and analysis.

---

## Wave 3 — Platform, Ecosystem, and Cloud
### Namel3ss Cloud
- One-click deploy from Studio or CLI.
- Managed hosting for apps, agents, flows, and schedulers.
- First-class observability dashboards for runs, cost tracking, and model usage.
- Environments for development, staging, and production.
- Governance controls for model selection, costs, and data policies.

### Plugin & Package Ecosystem
- A Namel3ss package registry for flows, agents, datasets, UI components, and integrations.
- Plugin API for data sources, vector stores, model providers, tools, and observability backends.
- Marketplace with free and premium plugins, including official certified integrations.

### Type System & Effects
- Gradual typing for models, flows, and data structures.
- Effect system for external I/O, model interactions, and structured agent behaviors.
- Optional strict mode for high-assurance flows.

### Deep Language Interoperability
- Python bridge for ML, data, and custom tooling.
- JS/TS bridge for embedding UI components or integrating with existing frontends.
- Ability to embed Namel3ss flows and agents inside other ecosystems.

---

## Vision
Namel3ss grows into more than a language.  
It becomes a complete AI-native development platform where:

- Intent becomes structure  
- Structure becomes behavior  
- Behavior becomes deployed experience  

— all with elegance, clarity, and confidence.

The destination is simple:  
Namel3ss becomes the world’s best way to think, build, and ship AI-native software.
