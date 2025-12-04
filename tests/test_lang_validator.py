from namel3ss import ir
from namel3ss.parser import parse_source
from namel3ss.lang.validator import validate_module


VALID_SOURCE = (
    'app "support":\n'
    '  entry_page "home"\n'
    'page "home":\n'
    '  route "/"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise":\n'
    '  model "default"\n'
    '  input from user_message\n'
)


def test_validator_accepts_valid_program():
    program = ir.ast_to_ir(parse_source(VALID_SOURCE))
    diags = validate_module(program)
    assert diags == []


def test_validator_catches_missing_fields_and_refs():
    invalid_source = (
        'app "support":\n'
        '  entry_page "home"\n'
        'page "home":\n'
        '  title "Home"\n'
        'flow "pipeline":\n'
        'ai "summarise":\n'
        '  input from user_message\n'
    )
    program = ir.ast_to_ir(parse_source(invalid_source))
    diags = validate_module(program)
    codes = {d.code for d in diags}
    assert "N3-1001" in codes  # missing required field (route/model_name)
    assert "N3-LANG-002" in codes  # flow has no steps
    assert any(d.hint for d in diags)
