# Learn Namel3ss — Preface

Namel3ss is an English-ish DSL and runtime for building AI-native applications: flows, UI, memory, RAG, tools, records/CRUD, and auth in a single `.ai` file. You describe intent; the runtime executes it; Studio lets you preview, run, and inspect. This book is for developers who code daily but are new to Namel3ss and want to ship assistants, RAG apps, CRUD dashboards, and tool-integrated flows.

Install with pip:
```bash
pip install namel3ss
```

How to use this book:
- Read sequentially to go from zero to production-ready.
- Copy every snippet into a `.ai` file; run with `n3` or open in Studio.
- Cross-references point to parser/runtime/tests/examples so you can verify behaviour.
- All code uses the modern English-ish `is`/`be` syntax defined in `src/namel3ss/parser.py`.
