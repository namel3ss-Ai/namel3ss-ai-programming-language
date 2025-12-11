import json
from textwrap import dedent

import pytest

from namel3ss import parser
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import ast_to_ir
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.tools.observability import (
    clear_tool_interceptors,
    register_after_tool_call,
    register_before_tool_call,
)


def _build_engine(ir):
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(ir, registry, tool_registry, router)
    metrics = MetricsTracker()
    return FlowEngine(
        program=ir,
        model_registry=registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
        metrics=metrics,
    )


def test_tool_retries_on_status(monkeypatch):
    code = dedent(
        '''
        tool is "unstable":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          retry:
            max_attempts is 3
            backoff is "constant"
            initial_delay is 0 seconds
            retry_on_status are [500]

        flow is "f":
          step is "call":
            kind is "tool"
            tool is "unstable"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)
    calls = {"count": 0}

    def fake_http(method, url, headers, body, timeout=None):
        calls["count"] += 1
        if calls["count"] < 3:
            return 500, {}, "fail"
        return 200, {}, json.dumps({"ok": True})

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    result = engine.run_flow(ir.flows["f"], exec_ctx)
    assert calls["count"] == 3
    assert result.state.get("last_output")["ok"] is True


def test_tool_timeout_override_applies(monkeypatch):
    code = dedent(
        '''
        tool is "slow":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          timeout is 9 seconds

        flow is "f":
          step is "call":
            kind is "tool"
            tool is "slow"
            timeout is 1
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)
    captured = {}

    def fake_http(method, url, headers, body, timeout=None):
        captured["timeout"] = timeout
        return 200, {}, json.dumps({"ok": True})

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    engine.run_flow(ir.flows["f"], exec_ctx)
    assert captured.get("timeout") == 1


def test_tool_auth_sets_bearer_header():
    code = dedent(
        '''
        tool is "auth_api":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          auth:
            kind is "bearer"
            token is "MY_TOKEN"

        flow is "f":
          step is "call":
            kind is "tool"
            tool is "auth_api"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)
    captured = {}

    def fake_http(method, url, headers, body, timeout=None):
        captured["headers"] = headers
        return 200, {}, json.dumps({"ok": True})

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    engine.run_flow(ir.flows["f"], exec_ctx)
    assert captured["headers"].get("Authorization") == "Bearer MY_TOKEN"


def test_tool_retries_skip_unsafe_by_default():
    code = dedent(
        '''
        tool is "poster":
          kind is "http_json"
          method is "POST"
          url is "https://api.example.com"
          retry:
            max_attempts is 3
            initial_delay is 0 seconds
            retry_on_status are [500]

        flow is "f":
          step is "call":
            kind is "tool"
            tool is "poster"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)
    calls = {"count": 0}

    def fake_http(method, url, headers, body, timeout=None):
        calls["count"] += 1
        return 500, {}, "fail"

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    result = engine.run_flow(ir.flows["f"], exec_ctx)
    assert calls["count"] == 1
    assert result.state.get("last_output")["ok"] is False


def test_tool_response_schema_validation_failure():
    code = dedent(
        '''
        tool is "user_api":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          response_schema:
            type is "object"
            required ["id", "email"]
            properties:
              id:
                type is "string"
              email:
                type is "string"

        flow is "f":
          step is "call":
            kind is "tool"
            tool is "user_api"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)

    def fake_http(method, url, headers, body, timeout=None):
        return 200, {}, json.dumps({"id": "123"})

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    result = engine.run_flow(ir.flows["f"], exec_ctx)
    output = result.state.get("last_output")
    assert output["ok"] is False
    assert "Response schema validation failed" in output.get("error", "")
    assert "user_api" in output.get("error", "")


def test_tool_response_schema_validation_success():
    code = dedent(
        '''
        tool is "user_api":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com"
          response_schema:
            type is "object"
            required ["id", "email"]
            properties:
              id:
                type is "string"
              email:
                type is "string"

        flow is "f":
          step is "call":
            kind is "tool"
            tool is "user_api"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)

    def fake_http(method, url, headers, body, timeout=None):
        return 200, {}, json.dumps({"id": "123", "email": "a@example.com"})

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    result = engine.run_flow(ir.flows["f"], exec_ctx)
    output = result.state.get("last_output")
    assert output["ok"] is True
    assert output["data"]["email"] == "a@example.com"


def test_tool_error_message_includes_context():
    code = dedent(
        '''
        tool is "unstable":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/resource"

        flow is "f":
          step is "call":
            kind is "tool"
            tool is "unstable"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)

    def fake_http(method, url, headers, body, timeout=None):
        return 500, {}, "server exploded"

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    result = engine.run_flow(ir.flows["f"], exec_ctx)
    output = result.state.get("last_output")
    assert output["ok"] is False
    assert "unstable" in output.get("error", "")
    assert "500" in output.get("error", "")
    assert "api.example.com/resource" in output.get("error", "")
    assert "server exploded" in output.get("error", "")


def test_tool_interceptors_receive_payloads():
    clear_tool_interceptors()
    captured: dict[str, dict] = {}

    def _before(tool, payload):
        captured["before"] = dict(payload)

    def _after(tool, payload):
        captured["after"] = dict(payload)

    register_before_tool_call(_before)
    register_after_tool_call(_after)
    code = dedent(
        '''
        tool is "observe_me":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/observe"
          logging is "debug"

        flow is "f":
          step is "call":
            kind is "tool"
            tool is "observe_me"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)

    def fake_http(method, url, headers, body, timeout=None):
        return 200, {"X-Test": "ok"}, json.dumps({"ok": True})

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    try:
        engine.run_flow(ir.flows["f"], exec_ctx)
    finally:
        clear_tool_interceptors()
    assert captured["before"]["method"] == "GET"
    assert captured["before"]["url"].endswith("/observe")
    assert captured["after"]["status"] == 200
    assert captured["after"]["raw_text"] == json.dumps({"ok": True})
