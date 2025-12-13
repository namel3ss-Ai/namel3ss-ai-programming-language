from urllib.parse import urlparse, parse_qsl
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
    return FlowEngine(
        program=ir,
        model_registry=registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
        metrics=metrics,
    )


def _run_and_capture(url_mode: str):
    code = dedent(
        f'''
        tool is "search":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/search"
          query is:
            ids: [1, 2, 3]
          query_encoding is "{url_mode}"

        flow is "f":
          step is "call":
            kind is "tool"
            tool is "search"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)
    captured = {}

    def fake_http(method, url, headers, body, timeout=None):
        captured["url"] = url
        return 200, {}, '{"ok": true}'

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    engine.run_flow(ir.flows["f"], exec_ctx)
    return captured["url"]


def test_query_encoding_repeat():
    url = _run_and_capture("repeat")
    parsed = urlparse(url)
    qs = parse_qsl(parsed.query, keep_blank_values=True)
    assert qs == [("ids", "1"), ("ids", "2"), ("ids", "3")]


def test_query_encoding_brackets():
    url = _run_and_capture("brackets")
    parsed = urlparse(url)
    qs = parse_qsl(parsed.query, keep_blank_values=True)
    assert qs == [("ids[]", "1"), ("ids[]", "2"), ("ids[]", "3")]


def test_query_encoding_csv():
    url = _run_and_capture("csv")
    parsed = urlparse(url)
    qs = parse_qsl(parsed.query, keep_blank_values=True)
    assert qs == [("ids", "1,2,3")]
