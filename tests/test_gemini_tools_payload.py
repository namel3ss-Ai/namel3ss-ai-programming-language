from textwrap import dedent

from namel3ss import parser
from namel3ss.ir import ast_to_ir
from namel3ss.tools.registry import ToolRegistry, build_ai_tool_specs
from namel3ss.ai.providers.gemini import GeminiProvider


def test_gemini_body_includes_tools(monkeypatch):
    code = dedent(
        """
        model is "gemini-1.5-pro":
          provider is "gemini_default"

        tool is "get_weather":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/weather"
          query:
            city: input.city

        ai is "assistant_with_tools":
          model is "gemini-1.5-pro"
          tools:
            - "get_weather"
        """
    )
    module = parser.parse_source(code)
    ir = ast_to_ir(module)
    ai = ir.ai_calls["assistant_with_tools"]

    registry = ToolRegistry()
    for tool in ir.tools.values():
        registry.register(tool)
    specs = build_ai_tool_specs(ai.tools, registry)

    captured_body = {}

    def fake_http(url, body, headers):
        nonlocal captured_body
        captured_body = {"url": url, "body": body, "headers": headers}
        return {"candidates": [{"content": {"parts": [{"text": "ok"}]}, "finish_reason": "STOP"}]}

    provider = GeminiProvider(name="gemini", api_key="test", http_client=fake_http)
    provider.chat_with_tools(
        messages=[{"role": "user", "content": "Hello"}],
        tools=[
            {
                "name": specs[0].name,
                "description": specs[0].description,
                "parameters": specs[0].parameters,
            }
        ],
        model="gemini-1.5-pro",
    )

    assert captured_body
    tools_payload = captured_body["body"].get("tools")
    assert tools_payload
    declarations = tools_payload[0].get("functionDeclarations") or []
    assert declarations
    assert declarations[0]["name"] == "get_weather"
