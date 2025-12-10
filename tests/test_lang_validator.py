from namel3ss import ir
from namel3ss.parser import parse_source
from namel3ss.lang.validator import validate_module


VALID_SOURCE = (
    'app is "support":\n'
    '  entry_page is "home"\n'
    'page is "home":\n'
    '  route "/"\n'
    'model is "default":\n'
    '  provider is "openai_default"\n'
    'ai is "summarise":\n'
    '  model is "default"\n'
    '  input from user_message\n'
)


def test_validator_accepts_valid_program():
    program = ir.ast_to_ir(parse_source(VALID_SOURCE))
    diags = validate_module(program)
    assert all(d.severity != "error" for d in diags)


def test_validator_catches_missing_fields_and_refs():
    invalid_source = (
        'app is "support":\n'
        '  entry_page is "home"\n'
        'page is "home":\n'
        '  title "Home"\n'
        'flow is "pipeline":\n'
        '  description "no steps yet"\n'
        'ai is "summarise":\n'
        '  input from user_message\n'
    )
    program = ir.ast_to_ir(parse_source(invalid_source))
    diags = validate_module(program)
    codes = {d.code for d in diags}
    assert "N3-1001" in codes  # missing required field (route/model_name)
    assert "N3-LANG-002" in codes  # flow has no steps
    assert any(d.hint for d in diags)
