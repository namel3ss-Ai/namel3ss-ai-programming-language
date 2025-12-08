from textwrap import dedent
import pytest

from namel3ss.lexer import Lexer
from namel3ss.parser import Parser
from namel3ss.ir import ast_to_ir, IRError
from namel3ss.tools.registry import ToolRegistry, ToolConfig


def build_program(code: str):
    module = Parser(Lexer(code).tokenize()).parse_module()
    return ast_to_ir(module)


def test_valid_tool_and_registry():
    code = dedent(
        '''
        tool is "get_weather":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/weather"
          query:
            city: input.city
        '''
    )
    program = build_program(code)
    reg = ToolRegistry()
    for tool in program.tools.values():
        reg.register(
            ToolConfig(
                name=tool.name,
                kind=tool.kind or "",
                method=tool.method or "",
                url_expr=tool.url_expr,
                headers=tool.headers,
                query_params=tool.query_params,
                body_fields=tool.body_fields,
                input_fields=list(tool.input_fields),
            )
        )
    cfg = reg.get("get_weather")
    assert cfg is not None
    assert cfg.kind == "http_json"
    assert cfg.method == "GET"
    assert cfg.url_expr.value == "https://api.example.com/weather"
    assert "city" in cfg.query_params


def test_missing_kind_errors():
    code = dedent(
        '''
        tool "get_weather":
          method "GET"
          url "https://api.example.com/weather"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(code)
    assert "N3L-960" in str(exc.value)


def test_invalid_kind_errors():
    code = dedent(
        '''
        tool "get_weather":
          kind "xyz"
          method "GET"
          url "https://api.example.com/weather"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(code)
    assert "N3L-960" in str(exc.value)


def test_missing_method_errors():
    code = dedent(
        '''
        tool "get_weather":
          kind "http_json"
          url "https://api.example.com/weather"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(code)
    assert "N3L-961" in str(exc.value)


def test_invalid_method_errors():
    code = dedent(
        '''
        tool "get_weather":
          kind "http_json"
          method "TRACE"
          url "https://api.example.com/weather"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(code)
    assert "N3L-961" in str(exc.value)


def test_missing_url_errors():
    code = dedent(
        '''
        tool "get_weather":
          kind "http_json"
          method "GET"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(code)
    assert "N3L-962" in str(exc.value)


def test_duplicate_tool_errors():
    code = dedent(
        '''
        tool "get_weather":
          kind "http_json"
          method "GET"
          url "https://api.example.com/weather"

        tool is "get_weather":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/weather"
        '''
    )
    with pytest.raises(IRError):
        build_program(code)
