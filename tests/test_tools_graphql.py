import asyncio
import json
from textwrap import dedent

from namel3ss.ir import IRProgram
from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir
from namel3ss.flows.engine import FlowEngine
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.graph import FlowNode, FlowState
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def _build_engine(src: str):
    module = parse_source(src)
    program: IRProgram = ast_to_ir(module)
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    return FlowEngine(program=program, model_registry=registry, tool_registry=tool_registry, agent_runner=agent_runner, router=router)


def test_graphql_tool_builds_body(monkeypatch):
    src = dedent(
        '''
    tool is "product_graphql":
      kind is "graphql"
      method is "POST"
      url is "https://api.example.com/graphql"
      query_template is "query Product($id: ID!) { product(id: $id) { id name } }"
      variables:
        id is input.id
    '''
    )
    engine = _build_engine(src)

    captured = {}

    async def fake_http(method, url, headers, body_bytes, timeout_seconds):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(body_bytes.decode("utf-8"))
        return 200, {"Content-Type": "application/json"}, json.dumps({"data": {"ok": True}})

    monkeypatch.setattr(engine, "_http_json_request", fake_http)

    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    runtime_ctx = engine._build_runtime_context(exec_ctx)
    node = FlowNode(
        id="t",
        kind="tool",
        config={"target": "product_graphql", "params": {"input": {"id": "123"}}},
        next_ids=[],
    )
    state = FlowState()
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(engine._execute_tool_call(node, state, runtime_ctx))
    finally:
        loop.close()

    assert result["ok"]
    assert captured["method"] == "POST"
    assert captured["body"]["variables"]["id"] == "123"
    assert "query" in captured["body"]
