# Namel3ss

![Version](https://img.shields.io/badge/version-0.6.9-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)
![Build](https://github.com/namel3ss-Ai/namel3ss-programming-language/actions/workflows/tests.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/namel3ss)
![Downloads](https://img.shields.io/badge/Downloads-pypi/month-green)

![AI-Native](https://img.shields.io/badge/AI--Native-Language-black)
![Studio](https://img.shields.io/badge/Open_in-Namel3ss_Studio-black)

**The AI-native language that feels crafted, not constructed.**  
Built for people who want software to feel intuitive — even poetic.

Write what you mean. Ship what you imagine.  
One DSL. One runtime. One Studio. A straight line from idea to experience.

---

**Start Here**  
[🚀 Quickstart](#quickstart) · [📘 Docs](#resources) · [📚 Book](#resources) · [🧩 Examples](#examples-gallery) · [🎨 Studio](#resources) · [🚀 Deployment](#resources)

**Jump to** Language · Features · Quickstart · Examples · Docs · Community

```
Intent → English DSL → Canonical AST → Runtime + Studio → Cloud / Desktop / Mobile
```

A straight line.  
From thought, to code, to creation.

---

## Why Namel3ss?
We believe AI-native software should feel like intent made real. Namel3ss exists to remove the plumbing: no glue code, no scattered configs. One DSL captures what you mean; one runtime and Studio bring it to life. Calm, direct, and human.

## What Makes Namel3ss Different
- English-style syntax that reads like you think  
- AI-native runtime with models, agents, and tools built in  
- Integrated Studio for UI, preview, and inspection  
- Canonical AST for stability and predictable execution  
- Deterministic builds for predictable shipping  
- One-command deploy to server, worker, cloud, desktop, and mobile  

## Guiding Principles
- Simplicity over complexity  
- Design before features  
- Consistency everywhere  
- The language should disappear behind your ideas  
- Tools should feel calm, not noisy  
- AI should feel native, never bolted on  

---

## A glimpse of the language
```ai
app "hello":
  entry_page "home"

page "home" at "/":
  section "hero":
    heading "Hello, Namel3ss"
    text "Design AI experiences with English-style clarity."

model "default":
  provider "openai:gpt-4.1-mini"

ai "summarize":
  model "default"
  input from "user_input"

flow "welcome":
  step "say":
    kind "ai"
    target "summarize"
```

It reads the way you think.  
Because building shouldn’t feel like translating.

---

## Designed like a product. Built like a platform.

✨ **English-Style Syntax**  
Simple. Natural. Human. You write intent — not boilerplate.

⚡ **AI-Native Runtime**  
Models, agents, tools, streaming, JSON mode. Not plugged in — built in.

🧩 **Flows & Agents**  
Real orchestration. Match, retry, schedule, listen, react. Every step traceable. Every decision explainable.

🎨 **UI & Studio**  
Pages, sections, inputs, buttons, components. A visual Studio crafted to disappear — so your ideas don’t.

🚀 **Deploy Everywhere**  
Cloud. Worker. Docker. Lambda. Cloudflare. Desktop. Mobile. One command: `n3 build`.

🛡 **Production Foundations**  
Canonical AST. Precise diagnostics. Strong linting. Tracing. Metrics. Logs. The invisible things that make software feel trustworthy.
---

## Architecture Overview
You describe intent in `.ai` files with the English-style DSL. A canonical AST normalizes that intent. The runtime executes flows, agents, tools, and models against the AST. Studio edits UI and logic with preview and inspection. The build system targets server, worker, cloud (AWS Lambda and Cloudflare), desktop, and mobile from one source of truth.

## Ecosystem Overview
- Language & runtime for flows, agents, UI, and deployment  
- Studio for visual editing, preview, and inspection  
- CLI for parse, lint, run, build, and deploy  
- Templates & examples to start quickly  
- Documentation & the Learn Namel3ss book for depth  
- Future: Namel3ss Cloud, plugins, and deeper integrations  

---

## Quickstart
A few minutes and you’re building.

```bash
pip install namel3ss

n3 parse examples/hello_world/hello_world.ai
n3 run hello-world --file examples/hello_world/hello_world.ai

n3 studio   # open namel3ss.local/studio or 127.0.0.1:4173/studio
n3 diagnostics --lint examples/hello_world/hello_world.ai

n3 build desktop
n3 build serverless-cloudflare app.ai --output-dir build/cloudflare
```

---

## 10-Minute Tutorial
1) **Create `app.ai`**  
   ```ai
   app "hello":
     entry_page "home"

   page "home" at "/":
     section "hero":
       heading "Hello"
   ```
2) **Add UI**  
   ```ai
   page "home" at "/":
     section "hero":
       heading "Hello"
       input "Your question" as question
       button "Ask":
         on click:
           do flow "answer"
   ```
3) **Add a model and AI block**  
   ```ai
   model "default":
     provider "openai:gpt-4.1-mini"

   ai "qa":
     model "default"
     input from question
   ```
4) **Wire a flow**  
   ```ai
   flow "answer":
     step "reply":
       kind "ai"
       target "qa"
   ```
5) **Run**  
   ```bash
   n3 run hello --file app.ai
   ```
6) **Open Studio**  
   ```bash
   n3 studio
   # open the printed URL to preview and inspect
   ```

---

## Examples Gallery
Each one is crafted to teach you something real.  
Open it. Read it. Modify it. Ship it.

🧠 RAG Q&A — [examples/rag_qa](examples/rag_qa)  
🤖 Support Bot — [examples/support_bot](examples/support_bot)  
🎨 UI & Pages — [examples/ui](examples/ui)  
🧩 Templates — [templates/](templates/)

They’re not demos. They’re starting points.

---

## Resources
📘 **Documentation Hub**  
Full Docs → [docs/index.md](docs/index.md)  
Language Spec → [docs/language_spec.md](docs/language_spec.md)  
CLI → [docs/api-surface.md](docs/api-surface.md)  
Deployment → [docs/reference/deployment.md](docs/reference/deployment.md)  
Studio → [docs/book/04-pages-and-ui.md](docs/book/04-pages-and-ui.md)

📚 **Learn Namel3ss — The Official Book**  
A calm, thoughtful, step-by-step guide to mastering the language.  
[docs/book/](docs/book/)

🛠 **Developer Tools**  
Studio → `n3 studio`  
VS Code Extension → [vscode-extension/README.md](vscode-extension/README.md)  
CLI → `n3 --help`
Media assets (images/videos for this README) → `assets/readme/`

---

## Roadmap Highlights
- We’re building multi-agent orchestration with shared memory and debugging tools.  
- We’re exploring Studio collaboration, blueprints, and AI-assisted refactors.  
- We’re preparing a Namel3ss Cloud deploy console for one-click shipping.  
- We’re designing a plugin and package marketplace for flows, agents, and UI components.  
- We’re advancing memory, evaluation, and safety guardrails across agents and flows.  
- We’re strengthening deployment targets with clearer observability out of the box.  

## Security & Privacy
Namel3ss does not collect or store your code by default. Everything runs locally unless you configure remote deployment or cloud targets. Security, safe AI usage, and guardrails remain core pillars of the roadmap.

---

## Community & Roadmap
Quietly ambitious. Deliberately bold.  
If you believe programming can feel better — you belong here.

Issues · Discussions · Roadmap → [GitHub](https://github.com/namel3ss/namel3ss-ai-programming-language)  
Contributions → See [CONTRIBUTING](CONTRIBUTING)

---

## Frequently Asked Questions
**Is Namel3ss a language or a framework?**  
It’s an AI-native language with an integrated runtime and tools.

**Is it open source? Which license?**  
Yes. MIT licensed.

**Can I use it commercially?**  
Yes, the MIT license permits commercial use.

**Does it replace Python/JavaScript or work alongside them?**  
It works alongside them; use Namel3ss for orchestration and UI while calling out to other stacks when needed.

**How does deployment work in simple terms?**  
Write once, then `n3 build <target>` for server, worker, Docker, AWS Lambda, Cloudflare, desktop, or mobile.

**Is Studio required, or can I use only the CLI?**  
Studio is optional. You can use only the CLI if you prefer.

---

## License
MIT License  
Copyright (c) 2025 Namel3ss Contributors  
See [LICENSE](LICENSE) for the full text.

<!-- README Phase RE++ implemented — premium text sections added. -->
