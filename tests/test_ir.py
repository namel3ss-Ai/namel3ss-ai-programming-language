import pytest

from namel3ss.ir import IRProgram, ast_to_ir
from namel3ss.errors import IRError
from namel3ss.parser import parse_source


PROGRAM_TEXT = (
    'app "support_portal":\n'
    '  description "Support portal for customer questions"\n'
    '  entry_page "home"\n'
    'page "home":\n'
    '  title "Home"\n'
    '  route "/"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
    '  input from user_message\n'
)


def test_ast_to_ir_produces_program():
    module = parse_source(PROGRAM_TEXT)
    program = ast_to_ir(module)
    assert isinstance(program, IRProgram)
    assert "support_portal" in program.apps
    assert program.apps["support_portal"].entry_page == "home"
    assert "home" in program.pages
    assert "default" in program.models
    assert "summarise_message" in program.ai_calls
    assert program.ai_calls["summarise_message"].model_name == "default"


def test_ast_to_ir_missing_page_raises():
    module = parse_source(
        'app "broken":\n'
        '  entry_page "missing"\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)
