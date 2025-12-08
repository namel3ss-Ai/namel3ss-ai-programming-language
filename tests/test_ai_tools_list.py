from textwrap import dedent

import pytest

from namel3ss import parser
from namel3ss.ast_nodes import AICallDecl
from namel3ss.ir import ast_to_ir, IRError


def test_ai_with_tools_list_parses_and_validates():
    code = dedent(
        """
        tool is "get_weather":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/weather"
          query:
            city: input.city

        model "gpt-4.1-mini":
          provider "openai:gpt-4.1-mini"

        ai is "assistant_with_tools":
          model is "gpt-4.1-mini"
          system is "You are a weather assistant."
          tools:
            - "get_weather"
        """
    )
    module = parser.parse_source(code)
    ai = next(dec for dec in module.declarations if isinstance(dec, AICallDecl))
    assert len(ai.tools) == 1
    assert ai.tools[0].internal_name == "get_weather"
    assert ai.tools[0].exposed_name == "get_weather"
    ir = ast_to_ir(module)
    binding = ir.ai_calls["assistant_with_tools"].tools[0]
    assert binding.internal_name == "get_weather"
    assert binding.exposed_name == "get_weather"


def test_ai_with_tool_alias_parses():
    code = dedent(
        """
        tool is "weather_api":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/weather"

        model "gpt-4.1-mini":
          provider "openai:gpt-4.1-mini"

        ai is "assistant_with_tools":
          model is "gpt-4.1-mini"
          tools:
            - tool is "weather_api"
              as is "get_weather"
        """
    )
    module = parser.parse_source(code)
    ai = next(dec for dec in module.declarations if isinstance(dec, AICallDecl))
    assert ai.tools[0].internal_name == "weather_api"
    assert ai.tools[0].exposed_name == "get_weather"
    ir = ast_to_ir(module)
    binding = ir.ai_calls["assistant_with_tools"].tools[0]
    assert binding.internal_name == "weather_api"
    assert binding.exposed_name == "get_weather"


def test_ai_with_unknown_tool_errors():
    code = dedent(
        """
        model "gpt-4.1-mini":
          provider "openai:gpt-4.1-mini"

        ai is "assistant_with_tools":
          model is "gpt-4.1-mini"
          tools:
            - "unknown_tool"
        """
    )
    module = parser.parse_source(code)
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "N3L-1410" in str(exc.value)


def test_ai_with_duplicate_alias_errors():
    code = dedent(
        """
        tool is "weather_api":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/weather"

        tool is "ticket_api":
          kind is "http_json"
          method is "POST"
          url is "https://api.example.com/tickets"

        model "gpt-4.1-mini":
          provider "openai:gpt-4.1-mini"

        ai is "assistant_with_tools":
          model is "gpt-4.1-mini"
          tools:
            - tool is "weather_api"
              as is "api_call"
            - tool is "ticket_api"
              as is "api_call"
        """
    )
    module = parser.parse_source(code)
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "N3L-1411" in str(exc.value)
