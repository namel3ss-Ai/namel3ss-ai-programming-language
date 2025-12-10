import pytest

from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir, IRModel, IRAgent, IRProgram
from namel3ss.errors import ParseError, Namel3ssError
from namel3ss.flows.engine import FlowEngine
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.tools.registry import ToolRegistry
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext


def _build_engine(program: IRProgram):
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    metrics = MetricsTracker()
    engine = FlowEngine(
        program=program,
        model_registry=registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
        metrics=metrics,
    )
    exec_ctx = ExecutionContext(
        app_name="test",
        request_id="req",
        tracer=None,
        tool_registry=tool_registry,
        metrics=metrics,
    )
    runtime_ctx = engine._build_runtime_context(exec_ctx)
    return engine, runtime_ctx


def _base_module() -> str:
    return (
        'frame is "users":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "users"\n'
        "\n"
        'record "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        "    name:\n"
        '      type "string"\n'
        "    status:\n"
        '      type "string"\n'
        "    created_at:\n"
        '      type "int"\n'
        "    is_active:\n"
        '      type "bool"\n'
    )


def test_order_limit_offset_behaviour():
    module = parse_source(
        _base_module()
        + "\n"
        'flow is "orders":\n'
        '  step is "seed_a":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u1"\n'
        '      name: "Alice"\n'
        '      status: "active"\n'
        "      created_at: 2\n"
        "      is_active: true\n"
        '  step is "seed_b":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u2"\n'
        '      name: "Bob"\n'
        '      status: "inactive"\n'
        "      created_at: 3\n"
        "      is_active: false\n"
        '  step is "seed_c":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u3"\n'
        '      name: "Charlie"\n'
        '      status: "active"\n'
        "      created_at: 1\n"
        "      is_active: true\n"
        '  step is "order_name":\n'
        '    find users where:\n'
        '      is_active is true\n'
        '    order users by name ascending\n'
        '  step is "order_multi":\n'
        '    find users where:\n'
        '      is_active is true\n'
        '    order users by status ascending, created_at descending\n'
        '  step is "limit_only":\n'
        '    find users where:\n'
        '      is_active is true\n'
        '    order users by name ascending\n'
        '    limit users to 1\n'
        '  step is "offset_only":\n'
        '    find users where:\n'
        '      is_active is true\n'
        '    order users by name ascending\n'
        '    offset users by 1\n'
        '  step is "limit_offset":\n'
        '    find users where:\n'
        '      is_active is true\n'
        '    order users by name ascending\n'
        '    offset users by 1\n'
        '    limit users to 1\n'
    )
    program = ast_to_ir(module)
    program.models["default"] = IRModel(name="default")
    program.agents["helper"] = IRAgent(name="helper")
    engine, runtime_ctx = _build_engine(program)
    flow = program.flows["orders"]
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})

    order_name = [r["id"] for r in result.state.get("step.order_name.output")]
    assert order_name == ["u1", "u3"]

    order_multi = [r["id"] for r in result.state.get("step.order_multi.output")]
    assert order_multi == ["u1", "u3"]

    limit_only = [r["id"] for r in result.state.get("step.limit_only.output")]
    assert limit_only == ["u1"]

    offset_only = [r["id"] for r in result.state.get("step.offset_only.output")]
    assert offset_only == ["u3"]

    limit_offset = [r["id"] for r in result.state.get("step.limit_offset.output")]
    assert limit_offset == ["u3"]


def test_invalid_limit_offset_raise_errors():
    module = parse_source(
        _base_module()
        + "\n"
        'flow is "bad":\n'
        '  step is "seed":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u1"\n'
        '      name: "Alice"\n'
        '      status: "active"\n'
        "      created_at: 2\n"
        "      is_active: true\n"
        '  step is "bad_limit":\n'
        '    find users where:\n'
        '      status is "active"\n'
        '    limit users to -1\n'
    )
    program = ast_to_ir(module)
    program.models["default"] = IRModel(name="default")
    program.agents["helper"] = IRAgent(name="helper")
    engine, runtime_ctx = _build_engine(program)
    flow = program.flows["bad"]
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.errors
    assert "non-negative number" in (result.errors[0].error or "")


def test_missing_sort_field_error():
    module = parse_source(
        _base_module()
        + "\n"
        'flow is "missing_field":\n'
        '  step is "seed":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u1"\n'
        '      name: "Alice"\n'
        '      status: "active"\n'
        "      created_at: 2\n"
        "      is_active: true\n"
        '  step is "order_missing":\n'
        '    find users where:\n'
        '      status is "active"\n'
        '    order users by missing_field descending\n'
    )
    program = ast_to_ir(module)
    program.models["default"] = IRModel(name="default")
    program.agents["helper"] = IRAgent(name="helper")
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["missing_field"], runtime_ctx.execution_context, initial_state={})
    assert result.errors
    assert "sort" in (result.errors[0].error or "")


def test_unknown_alias_in_order_parse_error():
    bad_source = (
        _base_module()
        + "\n"
        'flow is "bad_alias":\n'
        '  step is "oops":\n'
        '    order customers by name ascending\n'
    )
    with pytest.raises(ParseError):
        parse_source(bad_source)
