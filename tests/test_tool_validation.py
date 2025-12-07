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
          url_template is "https://api.example.com/weather?city={city}"
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
                url_template=tool.url_template or "",
                headers=tool.headers,
                body_template=tool.body_template,
            )
        )
    assert "get_weather" in reg.tools
    cfg = reg.get("get_weather")
    assert cfg.kind == "http_json"
    assert cfg.method == "GET"
    assert cfg.url_template.startswith("https://api.example.com")


def test_missing_kind_errors():
    code = dedent(
        '''
        tool "get_weather":
          method "GET"
          url_template "https://api.example.com/weather?city={city}"
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
          url_template "https://api.example.com/weather?city={city}"
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
          url_template "https://api.example.com/weather?city={city}"
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
          method "PUT"
          url_template "https://api.example.com/weather?city={city}"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(code)
    assert "N3L-961" in str(exc.value)


def test_missing_url_template_errors():
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
          url_template "https://api.example.com/weather?city={city}"

        tool is "get_weather":
          kind is "http_json"
          method is "GET"
          url_template is "https://api.example.com/weather?city={city}"
        '''
    )
    with pytest.raises(IRError):
        build_program(code)
