from textwrap import dedent

from namel3ss import parser
from namel3ss.ast_nodes import AICallDecl
from namel3ss.ir import ast_to_ir
from namel3ss.tools.registry import build_ai_tool_specs


def test_openai_body_includes_tools(monkeypatch):
    code = dedent(
        """
        model "gpt-4.1-mini":
          provider "openai:gpt-4.1-mini"

        tool is "get_weather":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/weather"
          query:
            city: input.city

        ai is "assistant_with_tools":
          model is "gpt-4.1-mini"
          tools:
            - "get_weather"
        """
    )
    module = parser.parse_source(code)
    ir = ast_to_ir(module)
    ai = ir.ai_calls["assistant_with_tools"]

    # Build tool specs and ensure OpenAI payload receives them
    from namel3ss.tools.registry import ToolRegistry
    from namel3ss.ai.providers.openai import OpenAIProvider

    # Prepare registry manually from IR tools
    reg = ToolRegistry()
    for tool in ir.tools.values():
        reg.register(tool)
    specs = build_ai_tool_specs(ai.tools, reg)

    captured_body = {}

    def fake_http(url, body, headers):
        nonlocal captured_body
        captured_body = body
        return {"choices": [{"message": {"content": "ok"}}]}

    provider = OpenAIProvider(name="openai", api_key="test", http_client=fake_http)
    provider.generate([], json_mode=False, model="gpt-4.1-mini", tools=[{
        "type": "function",
        "function": {
            "name": specs[0].name,
            "description": specs[0].description,
            "parameters": specs[0].parameters,
        }
    }])

    assert "tools" in captured_body
    assert captured_body["tools"][0]["function"]["name"] == "get_weather"
    assert "city" in captured_body["tools"][0]["function"]["parameters"]["properties"]


def test_openai_body_without_tools(monkeypatch):
    from namel3ss.ai.providers.openai import OpenAIProvider

    captured_body = {}

    def fake_http(url, body, headers):
        nonlocal captured_body
        captured_body = body
        return {"choices": [{"message": {"content": "ok"}}]}

    provider = OpenAIProvider(name="openai", api_key="test", http_client=fake_http)
    provider.generate([], json_mode=False, model="gpt-4.1-mini")
    assert "tools" not in captured_body
