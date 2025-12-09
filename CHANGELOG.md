# Changelog

## [Unreleased]
### Added
- Variables & Scope guidance: new book chapter, refreshed Naming Standard v1 links, and a focused example demonstrating locals, constants, step aliases, loops, and destructuring.
- Naming & Scope diagnostics: clearer messages for unknown identifiers, constants, loop vars, and step aliases aligned with English-first rules.
- Semantic versioning and IR version centralization, plus deprecation helper with optional strict mode.
- Golden example regression suite and documentation for versioning, releases, and roadmap.
- CLI exports for IR/FastAPI scaffolds and IR docs to support migrations.
- Lint engine with core English-style rules (unused bindings, shadowing, unreachable match branches, discouraged `=` in `let`), plus style and lint references.
- Example gallery programs demonstrating the stabilized language surface.
- Developer experience improvements: clearer parser diagnostics (with codes/hints), `n3 lint`/`n3 doctor` commands, and updated VS Code extension with lint-on-save, hover docs, and diagnostic links.

### Notes
- Language surface is frozen for the v1.0 English-style syntax; legacy symbolic forms have been removed. See Naming Standard v1 and Variables & Scope for the canonical forms.

## [3.0.0] - 2025-12-04
### Added
- Stable language, diagnostics, and runtime graph with CLI/HTTP access.
- Multi-provider model and embeddings routers, retrieval pipelines, and memory/RAG fusion.
- Flows 2.0 with parallel/for_each/try-catch/finally, timeouts, metrics, and fail-fast controls.
- Agents 2.0: reflection, debate, planning, evaluation, and team runners with memory hooks.
- Memory 2.0: episodic + semantic models, retention policies, summarization worker, and fusion APIs.
- Security 2.0: OAuth/API keys, RBAC, field-level masking, quotas.
- Observability: tracing, correlated logs, metrics registry, and observability APIs for Studio.
- Optimizer++: evaluation harness, suggestion engine, store, and accept/reject history.
- Plugin ecosystem: manifest/registry/SDK, marketplace-ready listing APIs, examples catalog, i18n hooks, Studio integration.

### Fixed
- Aligned docs, quickstarts, and ecosystem references for the 3.0.x line.

### Notes
- Public surfaces are stable for the 3.0.x releases; see `MIGRATING.md` for guidance when upgrading from earlier snapshots.
