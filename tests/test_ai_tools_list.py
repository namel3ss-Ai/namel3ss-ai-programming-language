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
          url_template is "https://api.example.com/weather?city={city}"

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
    assert ai.tools == ["get_weather"]
    ir = ast_to_ir(module)
    assert ir.ai_calls["assistant_with_tools"].tools == ["get_weather"]


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
    assert "N3L-970" in str(exc.value)
