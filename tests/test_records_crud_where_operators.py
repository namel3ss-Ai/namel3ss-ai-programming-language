import pytest

from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir, IRModel, IRProgram, IRAgent
from namel3ss.errors import ParseError
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


def test_where_operators_cover_comparisons_and_in():
    module = parse_source(
        'frame is "users":\n'
        '  backend "memory"\n'
        '  table "users"\n'
        "\n"
        'record "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        "    status:\n"
        '      type "string"\n'
        "    age:\n"
        '      type "int"\n'
        "    score:\n"
        '      type "float"\n'
        "    country:\n"
        '      type "string"\n'
        "    deleted_at:\n"
        '      type "datetime"\n'
        "\n"
        'flow is "where_tests":\n'
        '  step is "create_a":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u1"\n'
        '      status: "active"\n'
        "      age: 25\n"
        "      score: 80\n"
        '      country: "BE"\n'
        '  step is "create_b":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u2"\n'
        '      status: "inactive"\n'
        "      age: 17\n"
        "      score: 40\n"
        '      country: "US"\n'
        '      deleted_at: "2020-01-01T00:00:00"\n'
        '  step is "create_c":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "u3"\n'
        '      status: "active"\n'
        "      age: 65\n"
        "      score: 100\n"
        '      country: "NL"\n'
        '  step is "eq_status":\n'
        '    find users where:\n'
        '      status is "active"\n'
        '  step is "neq_status":\n'
        '    find users where:\n'
        '      status is not "inactive"\n'
        '  step is "gt_age":\n'
        '    find users where:\n'
        "      age is greater than 18\n"
        '  step is "ge_score":\n'
        '    find users where:\n'
        "      score is at least 80\n"
        '  step is "lt_age":\n'
        '    find users where:\n'
        "      age is less than 65\n"
        '  step is "le_score":\n'
        '    find users where:\n'
        "      score is at most 80\n"
        '  step is "in_country":\n'
        '    find users where:\n'
        '      country is one of ["BE", "NL"]\n'
        '  step is "null_deleted":\n'
        '    find users where:\n'
        "      deleted_at is null\n"
        '  step is "not_null_deleted":\n'
        '    find users where:\n'
        "      deleted_at is not null\n"
    )
    program = ast_to_ir(module)
    # Ensure runtime has basic model/agent entries for the engine plumbing
    program.models["default"] = IRModel(name="default")
    program.agents["helper"] = IRAgent(name="helper")
    engine, runtime_ctx = _build_engine(program)
    flow = program.flows["where_tests"]
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})

    eq_rows = result.state.get("step.eq_status.output")
    assert {r["id"] for r in eq_rows} == {"u1", "u3"}

    neq_rows = result.state.get("step.neq_status.output")
    assert {r["id"] for r in neq_rows} == {"u1", "u3"}

    gt_rows = result.state.get("step.gt_age.output")
    assert {r["id"] for r in gt_rows} == {"u1", "u3"}

    ge_rows = result.state.get("step.ge_score.output")
    assert {r["id"] for r in ge_rows} == {"u1", "u3"}

    lt_rows = result.state.get("step.lt_age.output")
    assert {r["id"] for r in lt_rows} == {"u1", "u2"}

    le_rows = result.state.get("step.le_score.output")
    assert {r["id"] for r in le_rows} == {"u1", "u2"}

    in_rows = result.state.get("step.in_country.output")
    assert {r["id"] for r in in_rows} == {"u1", "u3"}

    null_rows = result.state.get("step.null_deleted.output")
    assert {r["id"] for r in null_rows} == {"u1", "u3"}

    not_null_rows = result.state.get("step.not_null_deleted.output")
    assert {r["id"] for r in not_null_rows} == {"u2"}


def test_where_invalid_operator_has_clear_error():
    bad_source = (
        'frame is "users":\n'
        '  backend "memory"\n'
        '  table "users"\n'
        "\n"
        'record "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        "\n"
        'flow is "bad_where":\n'
        '  step is "fetch":\n'
        '    find users where:\n'
        '      status equals "active"\n'
    )
    with pytest.raises(ParseError) as exc:
        parse_source(bad_source)
    assert "WHERE" in str(exc.value) or "where" in str(exc.value)
