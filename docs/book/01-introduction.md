# 1. Introduction

## What is Namel3ss?
Namel3ss is an AI-native programming language and runtime. It gives you English-style syntax for apps, pages, flows, agents, tools, memory/RAG, and deployment—plus a consistent compiler, lint engine, and CLI/Studio workflow.

## Why an AI-focused DSL?
- **English-style clarity**: `let total be base plus bonus` is easy to read and audit.
- **Built-in AI/agents**: Models, streaming, JSON mode, and agents are first-class.
- **Automation & UI**: Flows, triggers, pages, and UI previews work together.
- **Deployment ready**: Build to server, worker, Docker, serverless (AWS/Cloudflare), desktop, and mobile targets from the same source.

## Core concepts at a glance
- **Bindings**: `let`, `set`, expressions, collections (with negative indices).
- **Flows & agents**: Steps calling AI, tools, or agents; control flow with match/retry.
- **UI pages**: `app` + `page` with sections, headings, text, inputs, buttons, and state.
- **Observability**: Logs, notes, checkpoints, diagnostics, lint.
- **Deployment**: `n3 build <target>` for desktop, mobile, serverless-aws, serverless-cloudflare, server, worker, docker.

## How to run examples
Examples live under `examples/`. Try:
```bash
n3 parse examples/hello_world/hello_world.ai
n3 run hello-world --file examples/hello_world/hello_world.ai
```
Open Studio with `n3 studio` to browse and edit them visually.

Where to go next:
- Chapter 2 (Getting Started) to set up your environment.
- Chapter 10 (Examples Walkthroughs) to explore working apps.
