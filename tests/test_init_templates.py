from pathlib import Path

from namel3ss.cli import main
from namel3ss.templates import list_templates, init_template
from namel3ss import lexer, parser, ir


def test_list_templates_contains_expected():
    templates = list_templates()
    assert "app-basic" in templates
    assert "app-rag" in templates
    assert "app-agents" in templates


def test_init_template_and_parse(tmp_path, monkeypatch):
    target = tmp_path / "proj"
    init_template("app-basic", target)
    assert (target / "app.ai").exists()
    source = (target / "app.ai").read_text(encoding="utf-8")
    tokens = lexer.Lexer(source, filename="app.ai").tokenize()
    module = parser.Parser(tokens).parse_module()
    program = ir.ast_to_ir(module)
    assert program.apps


def test_cli_init(tmp_path, monkeypatch, capsys):
    target = tmp_path / "proj2"
    main(["init", "app-basic", str(target), "--force"])
    assert (target / "app.ai").exists()
    out = capsys.readouterr().out
    assert "app-basic" in out
