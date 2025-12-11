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
from namel3ss.tools.runtime import rate_limiter


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


def test_tool_rate_limit_blocks_calls():
    rate_limiter.reset()
    code = dedent(
        '''
        tool is "limited":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/limited"
          rate_limit:
            max_calls_per_minute is 2
            burst is 2

        flow is "f":
          step is "call":
            kind is "tool"
            tool is "limited"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)
    captured = {"count": 0}

    def fake_http(method, url, headers, body, timeout=None):
        captured["count"] += 1
        return 200, {}, json.dumps({"ok": True})

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    result1 = engine.run_flow(ir.flows["f"], exec_ctx)
    result2 = engine.run_flow(ir.flows["f"], exec_ctx)
    result3 = engine.run_flow(ir.flows["f"], exec_ctx)
    assert captured["count"] == 2  # third should be blocked
    assert result1.state.get("last_output")["ok"] is True
    assert result2.state.get("last_output")["ok"] is True
    assert result3.state.get("last_output")["ok"] is False
    assert "rate limit" in (result3.state.get("last_output") or {}).get("error", "").lower()
