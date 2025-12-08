import pytest

from namel3ss.errors import IRError
from namel3ss.ir import IRProgram, ast_to_ir
from namel3ss.parser import parse_source


PROGRAM_TEXT = (
    'flow "support_pipeline":\n'
    '  step "classify":\n'
    '    kind "ai"\n'
    '    target "classify_ticket"\n'
    '  step "assign_helper":\n'
    '    kind "agent"\n'
    '    target "helper"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "classify_ticket":\n'
    '  model "default"\n'
    'agent "helper":\n'
    '  goal "Assist"\n'
)


def test_flow_ir_transforms():
    module = parse_source(PROGRAM_TEXT)
    program = ast_to_ir(module)
    assert isinstance(program, IRProgram)
    assert "support_pipeline" in program.flows
    flow = program.flows["support_pipeline"]
    assert flow.steps[0].target == "classify_ticket"
    assert flow.steps[1].kind == "agent"


def test_page_sections_ir():
    module = parse_source(
        'page "home":\n'
        '  section "hero":\n'
        '    component "text":\n'
        '      value "Welcome"\n'
    )
    program = ast_to_ir(module)
    page = program.pages["home"]
    assert page.sections[0].name == "hero"
    assert page.sections[0].components[0].props["value"] == "Welcome"


def test_plugin_ir_mapping():
    module = parse_source(
        'plugin "stripe":\n'
        '  description "Payments"\n'
    )
    program = ast_to_ir(module)
    assert "stripe" in program.plugins
    assert program.plugins["stripe"].description == "Payments"


def test_flow_invalid_reference_raises():
    module = parse_source(
        'flow "bad":\n'
        '  step "missing":\n'
        '    kind "agent"\n'
        '    target "ghost"\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)


def test_flow_invalid_tool_reference_raises():
    module = parse_source(
'flow "bad":\n'
'  step "missing":\n'
'    kind "tool"\n'
'    tool "unknown"\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)
