from pathlib import Path

from namel3ss import lexer, parser, ir


def _parse_file(path: Path):
    source = path.read_text(encoding="utf-8")
    tokens = lexer.Lexer(source, filename=str(path)).tokenize()
    module = parser.Parser(tokens).parse_module()
    return ir.ast_to_ir(module)


def test_hello_world_parses(tmp_path: Path):
    # use real example file
    path = Path("examples/hello_world/hello_world.ai")
    program = _parse_file(path)
    assert program is not None


def test_expressions_example_parses():
    path = Path("examples/expressions.ai")
    program = _parse_file(path)
    assert program is not None


def test_support_bot_parses():
    path = Path("examples/support_bot/support_bot.ai")
    program = _parse_file(path)
    assert program is not None


def test_getting_started_parses():
    path = Path("examples/getting_started/app.ai")
    program = _parse_file(path)
    assert program is not None
