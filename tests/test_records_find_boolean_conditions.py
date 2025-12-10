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
        "    country:\n"
        '      type "string"\n'
        "    is_active:\n"
        '      type "bool"\n'
        "    created_at:\n"
        '      type "int"\n'
    )


def _seed_block() -> str:
    return (
        '  step is "seed_a":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u1"\n'
        '      name: "Alice"\n'
        '      status: "regular"\n'
        '      country: "BE"\n'
        "      is_active: true\n"
        "      created_at: 3\n"
        '  step is "seed_b":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u2"\n'
        '      name: "Bob"\n'
        '      status: "regular"\n'
        '      country: "US"\n'
        "      is_active: true\n"
        "      created_at: 2\n"
        '  step is "seed_c":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u3"\n'
        '      name: "Carol"\n'
        '      status: "vip"\n'
        '      country: "BE"\n'
        "      is_active: false\n"
        "      created_at: 5\n"
        '  step is "seed_d":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u4"\n'
        '      name: "Dave"\n'
        '      status: "partner"\n'
        '      country: "BE"\n'
        "      is_active: true\n"
        "      created_at: 1\n"
    )


def _run_flow(flow_body: str, flow_name: str):
    module = parse_source(_base_module() + "\n" + flow_body)
    program = ast_to_ir(module)
    program.models["default"] = IRModel(name="default")
    program.agents["helper"] = IRAgent(name="helper")
    engine, runtime_ctx = _build_engine(program)
    return engine.run_flow(program.flows[flow_name], runtime_ctx.execution_context, initial_state={})


def test_explicit_and_or_conditions():
    flow_body = (
        'flow is "query":\n'
        f"{_seed_block()}"
        '  step is "query_users":\n'
        '    find users where:\n'
        '      is_active is true and country is "BE"\n'
        '      or status is "vip"\n'
    )
    result = _run_flow(flow_body, "query")
    ids = [r["id"] for r in result.state.get("step.query_users.output")]
    assert ids == ["u1", "u3", "u4"]  # (A and B) or C, insertion order preserved


def test_all_of_group():
    flow_body = (
        'flow is "query_all":\n'
        f"{_seed_block()}"
        '  step is "query_users":\n'
        '    find users where:\n'
        "      all of:\n"
        '        is_active is true\n'
        '        country is "BE"\n'
    )
    result = _run_flow(flow_body, "query_all")
    ids = [r["id"] for r in result.state.get("step.query_users.output")]
    assert ids == ["u1", "u4"]


def test_any_of_group():
    flow_body = (
        'flow is "query_any":\n'
        f"{_seed_block()}"
        '  step is "query_users":\n'
        '    find users where:\n'
        "      any of:\n"
        '        status is "vip"\n'
        '        status is "partner"\n'
    )
    result = _run_flow(flow_body, "query_any")
    ids = [r["id"] for r in result.state.get("step.query_users.output")]
    assert ids == ["u3", "u4"]


def test_nested_groups_and_or():
    flow_body = (
        'flow is "query_nested":\n'
        f"{_seed_block()}"
        '  step is "query_users":\n'
        '    find users where:\n'
        "      all of:\n"
        '        is_active is true\n'
        '        country is "BE"\n'
        "\n"
        "      or any of:\n"
        '        status is "vip"\n'
        '        status is "partner"\n'
    )
    result = _run_flow(flow_body, "query_nested")
    ids = [r["id"] for r in result.state.get("step.query_users.output")]
    assert ids == ["u1", "u3", "u4"]


def test_implicit_and_still_works():
    flow_body = (
        'flow is "query_and":\n'
        f"{_seed_block()}"
        '  step is "query_users":\n'
        '    find users where:\n'
        '      is_active is true\n'
        '      country is "BE"\n'
    )
    result = _run_flow(flow_body, "query_and")
    ids = [r["id"] for r in result.state.get("step.query_users.output")]
    assert ids == ["u1", "u4"]


def test_malformed_connector_raises_parse_error():
    source = (
        _base_module()
        + '\nflow is "bad":\n'
        "  step is \"query\":\n"
        "    find users where:\n"
        "      and status is \"vip\"\n"
    )
    with pytest.raises(ParseError):
        parse_source(source)


def test_empty_group_rejected():
    source = (
        _base_module()
        + '\nflow is "bad_group":\n'
        "  step is \"query\":\n"
        "    find users where:\n"
        "      all of:\n"
        "    \n"
    )
    with pytest.raises(ParseError):
        parse_source(source)


def test_non_boolean_condition_diagnostic():
    # Directly exercise the condition evaluator to surface the boolean diagnostic.
    program = ast_to_ir(parse_source(_base_module()))
    program.models["default"] = IRModel(name="default")
    program.agents["helper"] = IRAgent(name="helper")
    engine, _ = _build_engine(program)

    class WeirdEquals:
        def __eq__(self, other):
            return "maybe"

    row = {"id": WeirdEquals()}
    condition = {"type": "leaf", "field": "id", "op": "eq", "value": "anything"}
    with pytest.raises(Namel3ssError, match="true or false"):
        engine._condition_tree_matches(condition, row, "users")
