import pytest

from namel3ss.errors import IRError
from namel3ss.ir import IRProgram, ast_to_ir
from namel3ss.parser import parse_source


VALID_PROGRAM = (
    'page "home":\n'
    '  title "Home"\n'
    '  ai_call "summarise_message"\n'
    '  agent "helper"\n'
    '  memory "short_term"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
    'agent "helper":\n'
    '  goal "Assist"\n'
    'memory "short_term":\n'
    '  type "conversation"\n'
)


def test_page_ai_call_references_existing_call():
    module = parse_source(VALID_PROGRAM)
    program = ast_to_ir(module)
    assert isinstance(program, IRProgram)
    assert program.pages["home"].ai_calls == ["summarise_message"]
    assert program.pages["home"].agents == ["helper"]
    assert program.pages["home"].memories == ["short_term"]


def test_page_ai_call_missing_reference_raises():
    module = parse_source(
        'page "home":\n'
        '  ai_call "missing"\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)


def test_memory_invalid_type_raises():
    module = parse_source(
        'memory "bad":\n'
        '  type "unknown"\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)


def test_missing_agent_reference_raises():
    module = parse_source(
        'page "home":\n'
        '  agent "missing"\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)


def test_missing_memory_reference_raises():
    module = parse_source(
        'page "home":\n'
        '  memory "missing"\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)
