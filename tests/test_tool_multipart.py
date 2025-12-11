import re
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


def test_multipart_body_encoding():
    code = dedent(
        '''
        tool is "uploader":
          kind is "http_json"
          method is "POST"
          url is "https://api.example.com/upload"
          multipart is true
          body:
            file: payload
            note: "hello"

        flow is "f":
          step is "call":
            kind is "tool"
            tool is "uploader"
        '''
    )
    ir = ast_to_ir(parser.parse_source(code))
    engine = _build_engine(ir)
    captured = {}

    def fake_http(method, url, headers, body, timeout=None):
        captured["headers"] = headers
        captured["body"] = body
        return 200, {}, '{"ok": true}'

    engine._http_json_request = fake_http  # type: ignore
    exec_ctx = ExecutionContext(app_name="app", request_id="req", variables={"payload": b"FILEDATA"})
    engine.run_flow(ir.flows["f"], exec_ctx)

    content_type = captured["headers"].get("Content-Type") or captured["headers"].get("content-type")
    assert content_type is not None
    assert content_type.startswith("multipart/form-data")
    body_bytes = captured["body"]
    assert isinstance(body_bytes, (bytes, bytearray))
    body_text = body_bytes.decode("utf-8", errors="ignore")
    assert re.search(r'name="file"', body_text)
    assert "FILEDATA" in body_text
    assert 'name="note"' in body_text
    assert "hello" in body_text
