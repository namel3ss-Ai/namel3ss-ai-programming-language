from pathlib import Path

from namel3ss.cli import main


PROGRAM_TEXT = (
    'app "support_portal":\n'
    '  description "Support portal for customer questions"\n'
    '  entry_page "home"\n'
    'page "home":\n'
    '  title "Home"\n'
    '  route "/"\n'
    '  agent "helper"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
    '  input from user_message\n'
    'agent "helper":\n'
    '  goal "Assist"\n'
)


def write_program(tmp_path: Path) -> Path:
    program_file = tmp_path / "program.ai"
    program_file.write_text(PROGRAM_TEXT, encoding="utf-8")
    return program_file


def test_cli_parse_outputs_ast(tmp_path, capsys):
    program_file = write_program(tmp_path)
    main(["parse", str(program_file)])
    captured = capsys.readouterr().out
    assert '"declarations"' in captured
    assert '"support_portal"' in captured


def test_cli_ir_outputs_ir(tmp_path, capsys):
    program_file = write_program(tmp_path)
    main(["ir", str(program_file)])
    captured = capsys.readouterr().out
    assert '"apps"' in captured
    assert '"support_portal"' in captured


def test_cli_run_outputs_execution(tmp_path, capsys):
    program_file = write_program(tmp_path)
    main(["run", "support_portal", "--file", str(program_file)])
    captured = capsys.readouterr().out
    assert '"status": "ok"' in captured


def test_cli_serve_dry_run(capsys):
    main(["serve", "--dry-run"])
    captured = capsys.readouterr().out
    assert '"status": "ready"' in captured


def test_cli_run_agent(tmp_path, capsys):
    program_file = write_program(tmp_path)
    main(["run-agent", "--file", str(program_file), "--agent", "helper"])
    captured = capsys.readouterr().out
    assert '"agent_name": "helper"' in captured


def test_cli_run_flow(tmp_path, capsys):
    flow_program = (
        'flow "pipeline":\n'
        '  step "call":\n'
        '    kind "ai"\n'
        '    target "summarise_message"\n'
        'model "default":\n'
        '  provider "openai:gpt-4.1-mini"\n'
        'ai "summarise_message":\n'
        '  model "default"\n'
    )
    program_file = tmp_path / "flow.ai"
    program_file.write_text(flow_program, encoding="utf-8")
    main(["run-flow", "--file", str(program_file), "--flow", "pipeline"])
    captured = capsys.readouterr().out
    assert '"flow_name": "pipeline"' in captured


def test_cli_meta(tmp_path, capsys):
    program_file = write_program(tmp_path)
    main(["meta", "--file", str(program_file)])
    captured = capsys.readouterr().out
    assert '"models"' in captured


def test_cli_bundle_and_diagnostics_not_run_yet(tmp_path, capsys):
    program_file = write_program(tmp_path)
    main(["bundle", "--file", str(program_file), "--target", "server"])
    bundle_out = capsys.readouterr().out
    assert '"type": "server"' in bundle_out
    main(["diagnostics", "--file", str(program_file)])
    diag_out = capsys.readouterr().out
    assert "[warning]" in diag_out or "[error]" in diag_out or "No diagnostics found" in diag_out


def test_cli_lint_command(tmp_path, capsys):
    program_file = tmp_path / "lint.ai"
    program_file.write_text('flow "demo":\n  step "s":\n    let temp = 1\n', encoding="utf-8")
    main(["lint", str(program_file)])
    out = capsys.readouterr().out
    assert "N3-L001" in out
