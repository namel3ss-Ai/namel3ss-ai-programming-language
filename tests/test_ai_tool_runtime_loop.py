import json
from textwrap import dedent

import pytest

from namel3ss import parser
from namel3ss.ir import ast_to_ir
from namel3ss.runtime.context import ExecutionContext, execute_ai_call_with_registry
from namel3ss.ai.providers import ModelProvider
from namel3ss.ai.models import ModelResponse
from namel3ss.tools.registry import ToolConfig, ToolRegistry


class StubProvider(ModelProvider):
    def __init__(self, responses):
        super().__init__("stub")
        self.responses = responses
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        resp = self.responses.pop(0)
        return resp

    def stream(self, messages, **kwargs):
        raise NotImplementedError


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
          url_template is "https://api.example.com/weather?city={city}"

        ai is "assistant_with_tools":
          model is "gpt-4.1-mini"
          tools:
            - "get_weather"
        """
    )
    module = parser.parse_source(code)
    ir = ast_to_ir(module)
    ai_call = ir.ai_calls["assistant_with_tools"]

    first = ModelResponse(
        provider="stub",
        model="stub-model",
        messages=[],
        text="",
        raw={"tool_calls": [{"name": "get_weather", "arguments": {"city": "Brussels"}}]},
    )
    second = ModelResponse(
        provider="stub", model="stub-model", messages=[], text="It is sunny in Brussels.", raw={}
    )
    provider = StubProvider([first, second])
    registry = StubRegistry(provider)
    router = StubRouter()

    tool_registry = ToolRegistry()
    tool_registry.register(
        ToolConfig(
            name="get_weather",
            kind="http_json",
            method="GET",
            url_template="https://api.example.com/weather?city={city}",
            headers={},
        )
    )
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


def test_ai_tool_loop_limit_exceeded():
    code = dedent(
        """
        model "gpt-4.1-mini":
          provider "openai:gpt-4.1-mini"

        tool is "get_weather":
          kind is "http_json"
          method is "GET"
          url_template is "https://api.example.com/weather?city={city}"

        ai is "assistant_with_tools":
          model is "gpt-4.1-mini"
          tools:
            - "get_weather"
        """
    )
    module = parser.parse_source(code)
    ir = ast_to_ir(module)
    ai_call = ir.ai_calls["assistant_with_tools"]

    looping_resp = ModelResponse(
        provider="stub",
        model="stub-model",
        messages=[],
        text="",
        raw={"tool_calls": [{"name": "get_weather", "arguments": {"city": "Brussels"}}]},
    )
    provider = StubProvider([looping_resp, looping_resp, looping_resp, looping_resp])
    registry = StubRegistry(provider)
    router = StubRouter()
    tool_registry = ToolRegistry()
    tool_registry.register(
        ToolConfig(
            name="get_weather",
            kind="http_json",
            method="GET",
            url_template="https://api.example.com/weather?city={city}",
            headers={},
        )
    )
    ctx = ExecutionContext(
        app_name="app",
        request_id="req1",
        tool_registry=tool_registry,
        metadata={"mock_tool_results": {"get_weather": {"temp_c": 21}}},
    )
    with pytest.raises(Exception) as exc:
        execute_ai_call_with_registry(ai_call, registry, router, ctx)
    assert "N3F-971" in str(exc.value)
