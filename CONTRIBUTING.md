# Contributing to Namel3ss

Thank you for your interest in contributing to Namel3ss — the AI-native programming language and platform designed for clarity, safety, and expressive development.

Namel3ss is built with a simple mission:  
Make AI-native software development intuitive, safe, and beautifully integrated.

This document explains how to contribute, how the project is structured, and how contributions align with our long-term roadmap.

---

## 🌟 Core Principles
Before contributing, please understand the principles that shape every decision in Namel3ss:

1) **Simplicity Over Complexity**  
   Every feature should reduce conceptual burden. If it feels heavy, we redesign it.

2) **English-Style Expression**  
   Code should read the way you think. Naming and syntax must remain clear and natural.

3) **Safety by Default**  
   Flows, agents, and model interactions should guide users toward safe patterns automatically.

4) **Design as a Feature**  
   Studio, CLI, and DSL must feel intentional, calm, and consistent.

5) **AI-Native Foundations**  
   Agents, flows, models, memory, UI, and deployment must work together gracefully.

If your contribution aligns with these principles, you’re on the right path.

---

## 📁 Project Structure
```
namel3ss/
├─ src/namel3ss/           # DSL, parser, AST, runtime, compiler
├─ studio/                 # Visual editor (Preview, Inspector, AI tooling)
├─ examples/               # Canonical examples using modern syntax
├─ templates/              # App/flow/agent templates
├─ docs/                   # Documentation + Book
├─ tests/                  # Runtime, language, and integration tests
└─ cli/                    # n3 command-line interface
```

---

## 🚀 Contribution Areas (Based on Roadmap)
Namel3ss grows through waves of development, each building on the last. Here’s how you can help.

### Wave 1 — Strengthen the Core
**Language & Runtime Stability**
- Parser correctness
- Canonical AST consistency
- Legacy → modern transformer improvements
- Runtime execution semantics
- Error messages & diagnostics
- Standardization of agent/page/flow behaviors

**Developer Experience**
- n3 CLI commands and flags
- Studio stability (Code ↔ Inspector ↔ Preview mapping)
- AI UI generation improvements
- File system watcher reliability

**Documentation & Learning** (major tasks largely done)
- Improving examples
- Refining readability of docs
- Expanding tutorial clarity

### Wave 2 — AI-Native Power
**🧠 Multi-Agent Orchestration**
- Multi-agent flow patterns
- Agent communication channels
- Shared memory semantics
- Safety controls for autonomous agents

**🎨 AI-Native Studio**
- AI-assisted refactoring
- Flow explanation, guardrail suggestions
- Blueprint (template) generation
- Error highlighting and quick fixes

**🔐 Safety & Guardrails**
- Prompt injection detection
- Tool call security
- Safer endpoints
- Runtime limits and enforcement

**📊 Observability & Evaluation**
- Run Explorer timelines
- Flow metrics & cost tracking
- Regression evaluation harness
- Model output scoring utilities

### Wave 3 — Platform & Ecosystem
**☁️ Namel3ss Cloud**
- Deployment pipelines
- Environment configuration
- Remote logging & tracing frameworks
- Access control systems

**🧩 Plugin & Package Ecosystem**
- Plugin registry
- Integration SDK
- Third-party connectors
- Marketplace architecture

**🔤 Type System & Effects**
- Gradual typing
- Effect annotations
- Static reasoning about flows

**🔗 Deep Language Interop**
- Python/JS bridges
- Embedding Namel3ss components
- Inter-language toolchains

---

## 🧪 Testing Guidelines
- All changes must include appropriate tests:
  - Parser changes → grammar + AST tests
  - Runtime changes → flow/agent execution tests
  - Studio features → frontend + integration tests
  - CLI changes → snapshot and behavior tests
  - Docs/examples → runnable examples validated via CI
- Run the fast suite:
  ```bash
  python3 -m pytest -m "not slow" -q
  ```
- If your contribution affects performance or behavior, include benchmarks or reasoning notes.

---

## 🧭 How to Contribute
1. **Fork the repository**  
   Create a feature branch: `git checkout -b feature/my-change`
2. **Follow the modern syntax**  
   Never introduce new legacy forms. All examples, tests, and docs must use modern English-style syntax.
3. **Write clean, intentional code**  
   Descriptive names, minimal magic, consistent formatting, well-scoped functions.
4. **Add or update tests**  
   We do not accept changes without tests.
5. **Open a Pull Request**  
   Describe what changed, why it matters, how it aligns with the roadmap, and how you validated it.
6. **Participate in review**  
   Be open, respectful, and clear. We aim for collaboration, not speed.

---

## 🤝 Community Values
Namel3ss is built with intention:
- Respect contributors and their time.
- Prefer clarity over cleverness.
- Be generous with explanations.
- Celebrate thoughtful design.
- Leave the code better than you found it.

If you need help, open a GitHub Discussion or start a conversation in the community channel. We’re here to help you get started.

---

## 🌟 Thank You
Every contribution—big or small—moves Namel3ss closer to its vision:  
A language where AI-native experiences feel effortless, safe, and beautifully designed.  
Thank you for helping shape the future.
