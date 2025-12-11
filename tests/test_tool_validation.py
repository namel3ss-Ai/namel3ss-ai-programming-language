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
    assert cfg.kind in {"http", "http_json"}
    assert cfg.method == "GET"
    assert cfg.url_expr.value == "https://api.example.com/weather"
    assert "city" in cfg.query_params


def test_missing_kind_errors():
    code = dedent(
        '''
        tool is \"get_weather":
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
        tool is \"get_weather":
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
        tool is \"get_weather":
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
        tool is \"get_weather":
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
        tool is \"get_weather":
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
        tool is \"get_weather":
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


def test_tool_timeout_and_retry_parsing():
    code = dedent(
        '''
        tool is "fetch_order":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/orders/{id}"
          timeout is 5 seconds
          retry:
            max_attempts is 3
            backoff is "constant"
            initial_delay is 0.2 seconds
            max_delay is 1 seconds
            jitter is true
            retry_on_status are [500, 502]
        '''
    )
    program = build_program(code)
    tool = program.tools["fetch_order"]
    assert tool.timeout_seconds == 5
    assert tool.retry is not None
    assert tool.retry.max_attempts == 3
    assert tool.retry.backoff == "constant"
    assert tool.retry.initial_delay == 0.2
    assert tool.retry.max_delay == 1
    assert tool.retry.jitter is True
    assert tool.retry.retry_on_status == [500, 502]


def test_tool_retry_invalid_max_attempts():
    code = dedent(
        '''
        tool is "fetch_order":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/orders/{id}"
          retry:
            max_attempts is 0
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(code)
    assert "max_attempts" in str(exc.value)


def test_tool_retry_unknown_backoff_errors():
    code = dedent(
        '''
        tool is "fetch_order":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/orders/{id}"
          retry:
            backoff is "weird"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(code)
    assert "backoff" in str(exc.value)


def test_tool_auth_validation_errors():
    bearer_missing = dedent(
        '''
        tool is "github":
          kind is "http_json"
          method is "GET"
          url is "https://api.github.com"
          auth:
            kind is "bearer"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(bearer_missing)
    assert "missing token" in str(exc.value)

    bad_kind = dedent(
        '''
        tool is "github":
          kind is "http_json"
          method is "GET"
          url is "https://api.github.com"
          auth:
            kind is "unknown"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(bad_kind)
    assert "not supported" in str(exc.value)


def test_tool_response_schema_parsing_and_logging():
    code = dedent(
        '''
        tool is "fetch_user":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/users/{id}"
          response_schema:
            type is "object"
            required ["id", "email"]
            properties:
              id:
                type is "string"
              email:
                type is "string"
          logging is "debug"
        '''
    )
    program = build_program(code)
    tool = program.tools["fetch_user"]
    assert tool.response_schema is not None
    assert tool.response_schema.type == "object"
    assert tool.response_schema.required == ["id", "email"]
    assert tool.response_schema.properties["id"] == "string"
    assert tool.logging == "debug"


def test_tool_response_schema_invalid_type_errors():
    unknown_type = dedent(
        '''
        tool is "bad_schema":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          response_schema:
            type is "weird"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(unknown_type)
    assert "response_schema type" in str(exc.value)

    missing_property_type = dedent(
        '''
        tool is "missing_prop_type":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          response_schema:
            type is "object"
            properties:
              id:
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(missing_property_type)
    assert "must set type" in str(exc.value)

    array_required = dedent(
        '''
        tool is "array_bad_required":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          response_schema:
            type is "array"
            required ["id"]
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(array_required)
    assert "only use required" in str(exc.value)


def test_tool_logging_validation_errors():
    code = dedent(
        '''
        tool is "loud_tool":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          logging is "verbose"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(code)
    assert "logging must be one of" in str(exc.value)


def test_tool_rate_limit_validation_and_parsing():
    code = dedent(
        '''
        tool is "limited":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          rate_limit:
            max_calls_per_minute is 10
            burst is 5
        '''
    )
    program = build_program(code)
    tool = program.tools["limited"]
    assert tool.rate_limit is not None
    assert tool.rate_limit.max_calls_per_minute == 10
    assert tool.rate_limit.burst == 5

    bad = dedent(
        '''
        tool is "bad_limit":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          rate_limit:
            max_calls_per_minute is 0
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(bad)
    assert "max_calls_per_minute" in str(exc.value)


def test_tool_query_encoding_validation():
    code = dedent(
        '''
        tool is "search":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          query_encoding is "csv"
        '''
    )
    program = build_program(code)
    tool = program.tools["search"]
    assert tool.query_encoding == "csv"

    bad = dedent(
        '''
        tool is "search_bad":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          query_encoding is "invalid_mode"
        '''
    )
    with pytest.raises(IRError) as exc:
        build_program(bad)
    assert "query_encoding" in str(exc.value)
