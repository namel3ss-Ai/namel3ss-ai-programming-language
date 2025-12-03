# CLI Reference

Key commands (see `n3 --help`):
- `n3 parse <file>`: parse .ai and print AST.
- `n3 ir <file>`: emit IR.
- `n3 run --file <file> <app_name>`: run an app.
- `n3 run-agent --file <file> --agent <name>`: execute an agent.
- `n3 run-flow --file <file> --flow <name>`: execute a flow.
- `n3 diagnostics --file <file> [--strict] [--format json|text]`
- `n3 build-target <target> --file <file> --output-dir <dir>`: build deploy assets (server, worker, docker, serverless-aws, desktop, mobile).
- `n3 optimize <scan|list|apply|reject|overlays>`: optimizer CLI.
- `n3 init <template> [target-dir]`: scaffold from templates (app-basic, app-rag, app-agents).
- `n3 test-cov [pytest args...]`: run tests with coverage defaults.
