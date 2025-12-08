import json
from textwrap import dedent

import pytest

from namel3ss import ast_nodes, parser
from namel3ss.ir import IRAiCall, IRAiToolBinding, ast_to_ir
from namel3ss.runtime.context import ExecutionContext, execute_ai_call_with_registry
from namel3ss.ai.providers import ChatToolResponse, ModelProvider
from namel3ss.ai.models import ModelResponse
from namel3ss.tools.registry import ToolConfig, ToolRegistry


class StubProvider(ModelProvider):
    def __init__(self, responses):
        super().__init__("stub")
        self.responses = responses
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append({"method": "generate", "messages": [dict(m) for m in messages], "kwargs": kwargs})
        resp = self.responses.pop(0)
        return resp

    def stream(self, messages, **kwargs):
        raise NotImplementedError

    def chat_with_tools(self, messages, tools=None, tool_choice="auto", **kwargs):
        self.calls.append(
            {"method": "chat", "messages": [dict(m) for m in messages], "kwargs": {"tools": tools, "tool_choice": tool_choice, **kwargs}}
        )
        resp = self.responses.pop(0)
        if isinstance(resp, ModelResponse):
            return ChatToolResponse(final_text=resp.text, tool_calls=[], raw=resp.raw, finish_reason=resp.finish_reason)
        return ChatToolResponse(
            final_text=resp.get("final_text"),
            tool_calls=resp.get("tool_calls") or [],
            raw=resp.get("raw"),
            finish_reason=resp.get("finish_reason"),
        )


class StubRegistry:
    def __init__(self, provider):
        self.provider = provider

    def get_model_config(self, name):
        class Cfg:
            def __init__(self, model):
                self.name = model
                self.model = model
                self.base_url = None
                self.response_path = None
                self.options = {}
                self.provider = "stub"

        return Cfg(name)

    def get_provider_for_model(self, name):
        return self.provider


class StubRouter:
    def select_model(self, logical_name=None):
        class Sel:
            def __init__(self, name):
                self.model_name = name
                self.provider_name = "stub"
                self.actual_model = name

        return Sel(logical_name or "stub-model")


def test_ai_tool_loop_happy_path():
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
    ai_call = ir.ai_calls["assistant_with_tools"]

    first = {"tool_calls": [{"name": "get_weather", "arguments": {"city": "Brussels"}}], "final_text": ""}
    second = {"tool_calls": [], "final_text": "It is sunny in Brussels."}
    provider = StubProvider([first, second])
    registry = StubRegistry(provider)
    router = StubRouter()

    tool_registry = ToolRegistry()
    for tool in ir.tools.values():
        tool_registry.register(tool)
    ctx = ExecutionContext(
        app_name="app",
        request_id="req1",
        tool_registry=tool_registry,
        metadata={"mock_tool_results": {"get_weather": {"temp_c": 21, "condition": "Sunny"}}},
    )
    result = execute_ai_call_with_registry(ai_call, registry, router, ctx)
    assert "provider_result" in result
    assert provider.calls[0]["kwargs"].get("tools")  # tools attached
    assert provider.calls[1]["kwargs"].get("tools")  # second call after tool
    tool_msg = provider.calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool"
    assert json.loads(tool_msg["content"]) == {"temp_c": 21, "condition": "Sunny"}


def test_ai_tool_loop_unknown_tool_errors():
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
    ai_call = ir.ai_calls["assistant_with_tools"]

    bad_resp = {"tool_calls": [{"name": "missing_alias", "arguments": {"city": "Brussels"}}], "final_text": ""}
    provider = StubProvider([bad_resp])
    registry = StubRegistry(provider)
    router = StubRouter()
    tool_registry = ToolRegistry()
    for tool in ir.tools.values():
        tool_registry.register(tool)
    ctx = ExecutionContext(
        app_name="app",
        request_id="req1",
        tool_registry=tool_registry,
        metadata={"mock_tool_results": {"get_weather": {"temp_c": 21}}},
    )
    with pytest.raises(Exception) as exc:
        execute_ai_call_with_registry(ai_call, registry, router, ctx)
    assert "N3F-972" in str(exc.value)


def test_step_tools_mode_none_disables_tool_loop():
    ai_call = IRAiCall(
        name="assistant_with_tools",
        model_name="gpt-4.1-mini",
        input_source="Hello",
        tools=[IRAiToolBinding(internal_name="get_weather", exposed_name="get_weather")],
    )
    model_resp = ModelResponse(provider="stub", model="stub", messages=[], text="No tools", raw={})
    provider = StubProvider([model_resp])
    registry = StubRegistry(provider)
    router = StubRouter()
    tool_registry = ToolRegistry()
    tool_registry.register(
        ToolConfig(
            name="get_weather",
            kind="http_json",
            method="GET",
            url_expr=ast_nodes.Literal(value="https://example.com"),
        )
    )
    ctx = ExecutionContext(app_name="app", request_id="req1", tool_registry=tool_registry)
    result = execute_ai_call_with_registry(ai_call, registry, router, ctx, tools_mode="none")
    assert result["provider_result"]["result"] == "No tools"
    assert provider.calls[0]["method"] == "generate"
