import asyncio
from textwrap import dedent

from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.graph import FlowNode, FlowState
from namel3ss.ir import IRProgram, ast_to_ir
from namel3ss.parser import parse_source
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def add(a, b):
    return a + b


def _build_engine(src: str):
    module = parse_source(src)
    program: IRProgram = ast_to_ir(module)
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    return FlowEngine(program=program, model_registry=registry, tool_registry=tool_registry, agent_runner=agent_runner, router=router)


def test_local_function_tool_executes():
    src = dedent(
        '''
    tool is "adder":
      kind is "local_function"
      function is "test_tools_local_function.add"
      input_fields are ["a", "b"]
    '''
    )
    engine = _build_engine(src)
    exec_ctx = ExecutionContext(app_name="app", request_id="req")
    runtime_ctx = engine._build_runtime_context(exec_ctx)
    node = FlowNode(
        id="t",
        kind="tool",
        config={"target": "adder", "params": {"input": {"a": 2, "b": 3}}},
        next_ids=[],
    )
    state = FlowState()
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(engine._execute_tool_call(node, state, runtime_ctx))
    finally:
        loop.close()
    assert result["ok"]
    assert result["data"] == 5
