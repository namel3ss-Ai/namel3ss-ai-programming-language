from pathlib import Path

from namel3ss.cli import main


PROGRAM_TEXT = (
    'page "home":\n'
    '  title "Home"\n'
    '  ai_call "summarise_message"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
    'agent "helper":\n'
    '  goal "Assist"\n'
    'memory "short_term":\n'
    '  type "conversation"\n'
)


def write_program(tmp_path: Path) -> Path:
    program_file = tmp_path / "program.ai"
    program_file.write_text(PROGRAM_TEXT, encoding="utf-8")
    return program_file


def test_cli_graph_outputs_nodes_and_edges(tmp_path, capsys):
    program_file = write_program(tmp_path)
    main(["graph", str(program_file)])
    captured = capsys.readouterr().out
    assert '"nodes"' in captured
    assert '"edges"' in captured
    assert "AI_CALL_REF" in captured
