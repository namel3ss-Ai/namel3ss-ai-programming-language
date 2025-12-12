from pathlib import Path

import pytest

from namel3ss.cli import main


PROGRAM_TEXT = (
    'app is "support_portal":\n'
    '  description "Support portal for customer questions"\n'
    '  entry_page is "home"\n'
    'page is "home":\n'
    '  title "Home"\n'
    '  route "/"\n'
    '  agent "helper"\n'
    'model is "default":\n'
    '  provider is "openai_default"\n'
    'ai is "summarise_message":\n'
    '  model is "default"\n'
    '  input from user_message\n'
    'agent is "helper":\n'
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
        'flow is "pipeline":\n'
        '  step is "call":\n'
        '    kind is "ai"\n'
        '    target is "summarise_message"\n'
        'model is "default":\n'
        '  provider is "openai_default"\n'
        'ai is "summarise_message":\n'
        '  model is "default"\n'
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
    program_file.write_text('flow is "demo":\n  step is "s":\n    let temp be 1\n', encoding="utf-8")
    main(["lint", str(program_file)])
    out = capsys.readouterr().out
    assert "N3-L001" in out


def test_cli_macro_expand_outputs_expansion(tmp_path, capsys):
    src = (
        'macro is "hello" using ai "codegen":\n'
        '  description "hello macro"\n'
        '  sample "flow is \\"hello_flow\\":\\n  step is \\"s\\":\\n    log info \\"hi\\""\n'
        "\n"
        'use macro is "hello"\n'
    )
    path = tmp_path / "macro.ai"
    path.write_text(src, encoding="utf-8")
    main(["macro", "expand", str(path)])
    out = capsys.readouterr().out
    assert 'flow is "hello_flow"' in out


def test_cli_macro_expand_failure(tmp_path, capsys):
    src = (
        'macro is "bad" using ai "codegen":\n'
        '  description "bad macro"\n'
        '  sample "flow \\"legacy\\":\\n  step is \\"s\\":\\n    log info \\"hi\\""\n'
        "\n"
        'use macro is "bad"\n'
    )
    path = tmp_path / "macro_bad.ai"
    path.write_text(src, encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        main(["macro", "expand", str(path)])
    msg = str(excinfo.value)
    assert "macro" in msg.lower() and "bad" in msg.lower()


def test_cli_macro_test_pass_and_fail(tmp_path, capsys):
    src = (
        'macro is "rec" using ai "codegen":\n'
        '  description "record macro"\n'
        '  sample "\\nframe is \\"things_frame\\":\\n  backend is \\"memory\\"\\n  table is \\"things\\"\\n\\nrecord is \\"Thing\\":\\n  frame is \\"things_frame\\"\\n  fields:\\n    thing_id:\\n      type is \\"uuid\\"\\n      primary_key is true\\n      required is true\\n"\n'
        "\n"
        'macro test is "record_ok":\n'
        "  use macro is \"rec\"\n"
        '  expect record "Thing"\n'
        "\n"
        'macro test is "record_missing_flow":\n'
        "  use macro is \"rec\"\n"
        '  expect flow "missing"\n'
    )
    path = tmp_path / "macro_tests.ai"
    path.write_text(src, encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["macro", "test", str(path)])
    output = capsys.readouterr().out
    assert "record_missing_flow" in output or "missing" in output
    # run again with only passing test filtered by name flag via trimmed file
    passing = (
        'macro is "rec" using ai "codegen":\n'
        '  description "record macro"\n'
        '  sample "\\nframe is \\"things_frame\\":\\n  backend is \\"memory\\"\\n  table is \\"things\\"\\n\\nrecord is \\"Thing\\":\\n  frame is \\"things_frame\\"\\n  fields:\\n    thing_id:\\n      type is \\"uuid\\"\\n      primary_key is true\\n      required is true\\n"\n'
        "\n"
        'macro test is "record_ok":\n'
        "  use macro is \"rec\"\n"
        '  expect record "Thing"\n'
    )
    path_ok = tmp_path / "macro_tests_ok.ai"
    path_ok.write_text(passing, encoding="utf-8")
    main(["macro", "test", str(path_ok)])
    ok_out = capsys.readouterr().out
    assert "Passed 1 macro test" in ok_out
