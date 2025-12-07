from textwrap import dedent

import pytest

from namel3ss.errors import ParseError
from namel3ss.lexer import Lexer
from namel3ss.parser import Parser
from namel3ss.ir import ast_to_ir, IRError


def test_parse_flow_tool_step_with_args():
    code = dedent(
        '''
        tool is "get_weather":
          kind is "http_json"
          method is "GET"
          url_template is "https://api.example.com/weather?city={city}"

        flow is "check_weather":
          step is "call_tool":
            kind is "tool"
            target is "get_weather"
            args:
              city: state.city
        '''
    )
    module = Parser(Lexer(code).tokenize()).parse_module()
    flow = next(dec for dec in module.declarations if dec.__class__.__name__ == "FlowDecl")
    step = flow.steps[0]
    assert step.kind == "tool"
    assert step.target == "get_weather"
    assert "args" in step.params
    assert "city" in step.params["args"]


def test_missing_tool_target_errors():
    code = dedent(
        '''
        flow "f":
          step "call":
            kind "tool"
        '''
    )
    with pytest.raises(ParseError) as exc:
        Parser(Lexer(code).tokenize()).parse_module()
    assert "N3L-963" in str(exc.value)


def test_unknown_tool_reference_errors():
    code = dedent(
        '''
        flow "f":
          step "call":
            kind "tool"
            target "not_declared"
        '''
    )
    module = Parser(Lexer(code).tokenize()).parse_module()
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "N3L-964" in str(exc.value)

