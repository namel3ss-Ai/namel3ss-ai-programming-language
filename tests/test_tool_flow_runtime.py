import json
import pytest
from textwrap import dedent

from namel3ss import parser
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import ast_to_ir
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def _build_engine(ir):
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(ir, registry, tool_registry, router)
    metrics = MetricsTracker()
    engine = FlowEngine(
        program=ir,
        model_registry=registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
        metrics=metrics,
    )
    return engine


def test_tool_flow_runtime_success(monkeypatch):
    code = dedent(
        '''
        tool is "get_weather":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/weather"
          query:
            city: input.city

        flow is "check_weather":
          step is "call_tool":
            kind is "tool"
            tool is "get_weather"
            input:
              city: "Brussels"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)

    captured = {}

    def fake_http(method, url, headers, body):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = body
        return 200, {"Content-Type": "application/json"}, json.dumps({"temp_c": 21, "condition": "Sunny"})

    engine._http_json_request = fake_http  # type: ignore

    last_ctx = {}
    orig_build = engine._build_runtime_context

    def patched_build(ctx, stream_callback=None):
        runtime_ctx = orig_build(ctx, stream_callback=stream_callback)
        last_ctx["ctx"] = runtime_ctx
        return runtime_ctx

    engine._build_runtime_context = patched_build  # type: ignore

    exec_ctx = ExecutionContext(app_name="test", request_id="req")
    result = engine.run_flow(ir.flows["check_weather"], exec_ctx, initial_state={})
    assert result.state is not None
    last_output = result.state.get("last_output")
    assert last_output["ok"] is True
    assert last_output["data"] == {"temp_c": 21, "condition": "Sunny"}
    assert captured["method"] == "GET"
    assert "Brussels" in captured["url"]

    # event log should contain start/end entries
    events = last_ctx["ctx"].event_logger.frames._store.get("event_log", [])  # type: ignore[attr-defined]
    kinds = [e.get("event_type") for e in events if e.get("kind") == "tool"]
    assert "start" in kinds and "end" in kinds


def test_tool_flow_runtime_missing_arg_errors(monkeypatch):
    code = dedent(
        '''
        tool "get_weather":
          kind "http_json"
          method "GET"
          url "https://api.example.com/weather"
          query:
            city: input.city

        flow "check_weather":
          step "call_tool":
            kind "tool"
            tool "get_weather"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)
    exec_ctx = ExecutionContext(app_name="test", request_id="req")
    result = engine.run_flow(ir.flows["check_weather"], exec_ctx, initial_state={})
    assert result.errors, "Expected error for missing city arg"
    assert any("N3F-965" in err.error for err in result.errors)


def test_tool_flow_runtime_http_error(monkeypatch):
    code = dedent(
        '''
        tool "get_weather":
          kind "http_json"
          method "GET"
          url "https://api.example.com/weather"
          query:
            city: input.city

        flow "check_weather":
          step "call_tool":
            kind "tool"
            tool "get_weather"
            input:
              city: "Nowhere"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)

    def fake_http(method, url, headers, body):
        return 500, {"Content-Type": "application/json"}, json.dumps({"error": "bad request"})

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="test", request_id="req")
    result = engine.run_flow(ir.flows["check_weather"], exec_ctx, initial_state={})
    assert not result.errors, "HTTP error should surface via step output"
    last_output = result.state.get("last_output")
    assert last_output["ok"] is False
    assert last_output["status"] == 500
