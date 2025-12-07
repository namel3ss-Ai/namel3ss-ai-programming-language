from textwrap import dedent

from namel3ss.lexer import Lexer
from namel3ss.parser import Parser


def test_parse_tool_basic():
    code = dedent(
        '''
        tool "get_weather":
          kind "http_json"
          method "GET"
          url_template "https://api.example.com/weather?city={city}"
        '''
    )
    module = Parser(Lexer(code).tokenize()).parse_module()
    tool = next(dec for dec in module.declarations if dec.__class__.__name__ == "ToolDeclaration")
    assert tool.name == "get_weather"
    assert tool.kind == "http_json"
    assert tool.method == "GET"
    assert tool.url_template == "https://api.example.com/weather?city={city}"
    assert tool.headers == {}
    assert tool.body_template is None


def test_parse_tool_english_with_headers():
    code = dedent(
        '''
        tool is "get_weather":
          kind is "http_json"
          method is "GET"
          url_template is "https://api.example.com/weather?city={city}"
          headers:
            "x-api-key": config.weather_api_key
        '''
    )
    module = Parser(Lexer(code).tokenize()).parse_module()
    tool = next(dec for dec in module.declarations if dec.__class__.__name__ == "ToolDeclaration")
    assert tool.name == "get_weather"
    assert tool.kind == "http_json"
    assert tool.method == "GET"
    assert tool.url_template == "https://api.example.com/weather?city={city}"
    assert "x-api-key" in tool.headers
    # header value stored as expression (Identifier chain)
    expr = tool.headers["x-api-key"]
    assert expr is not None
    assert tool.body_template is None
