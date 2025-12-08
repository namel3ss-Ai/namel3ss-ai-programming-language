from textwrap import dedent

from namel3ss.lexer import Lexer
from namel3ss.parser import Parser
from namel3ss import ast_nodes


def test_parse_tool_with_query_and_url_expr():
    code = dedent(
        '''
        tool "get_weather":
          kind "http_json"
          method "GET"
          url "https://api.example.com/weather"
          query:
            city: input.city
        '''
    )
    module = Parser(Lexer(code).tokenize()).parse_module()
    tool = next(dec for dec in module.declarations if isinstance(dec, ast_nodes.ToolDeclaration))
    assert tool.name == "get_weather"
    assert tool.kind == "http_json"
    assert tool.method == "GET"
    assert isinstance(tool.url_expr, ast_nodes.Literal)
    assert tool.url_expr.value == "https://api.example.com/weather"
    assert "city" in tool.query_params
    city_expr = tool.query_params["city"]
    assert isinstance(city_expr, ast_nodes.RecordFieldAccess)
    assert isinstance(city_expr.target, ast_nodes.Identifier)
    assert city_expr.target.name == "input"
    assert city_expr.field == "city"
    assert tool.headers == {}
    assert tool.body_fields == {}


def test_parse_tool_with_headers_and_body_block():
    code = dedent(
        '''
        tool is "create_ticket":
          kind is "http_json"
          method is "POST"
          url is "https://api.example.com/tickets"
          headers:
            Accept: "application/json"
          body:
            title: input.title
            api_key: secret.SERVICE_KEY
        '''
    )
    module = Parser(Lexer(code).tokenize()).parse_module()
    tool = next(dec for dec in module.declarations if isinstance(dec, ast_nodes.ToolDeclaration))
    assert tool.name == "create_ticket"
    assert tool.method == "POST"
    assert "Accept" in tool.headers
    assert isinstance(tool.headers["Accept"], ast_nodes.Literal)
    title_expr = tool.body_fields["title"]
    assert isinstance(title_expr, ast_nodes.RecordFieldAccess)
    assert isinstance(title_expr.target, ast_nodes.Identifier)
    assert title_expr.target.name == "input"
    assert title_expr.field == "title"
    api_expr = tool.body_fields["api_key"]
    assert isinstance(api_expr, ast_nodes.RecordFieldAccess)
    assert isinstance(api_expr.target, ast_nodes.Identifier)
    assert api_expr.target.name == "secret"
    assert api_expr.field == "SERVICE_KEY"
