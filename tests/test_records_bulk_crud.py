import pytest

from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.errors import Namel3ssError, ParseError
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import IRFlow, IRFlowLoop, IRFlowStep, IRFrame, IRModel, IRProgram, IRRecord, IRRecordField, IRAgent, ast_to_ir
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.parser import parse_source
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


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


def _parse_program(source: str) -> IRProgram:
    module = parse_source(source)
    program = ast_to_ir(module)
    assert program.flows, "expected at least one flow in program"
    return program


def test_bulk_create_uses_state_list_and_returns_rows():
    source = (
        'frame is "users":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "users"\n'
        'record is "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        "    email:\n"
        '      type "string"\n'
        '      required true\n'
        "    name:\n"
        '      type "string"\n'
        '      default "Anonymous"\n'
        'flow is "bulk_seed":\n'
        '  step is "insert_many":\n'
        '    create many users from state.new_users\n'
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context
    initial_state = {
        "new_users": [
            {"id": "user-a", "email": "a@example.com"},
            {"id": "user-b", "email": "b@example.com"},
        ]
    }
    result = engine.run_flow(program.flows["bulk_seed"], context, initial_state=initial_state)
    output = result.state.get("step.insert_many.output")
    assert output and len(output) == 2
    rows = engine.frame_registry.query("users")
    assert len(rows) == 2
    assert {row["id"] for row in rows} == {"user-a", "user-b"}


def test_bulk_create_uniqueness_violation_does_not_insert_rows():
    source = (
        'frame is "users":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "users"\n'
        'record is "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        "    email:\n"
        '      type "string"\n'
        '      required true\n'
        '      must be unique\n'
        'flow is "bulk_seed":\n'
        '  step is "insert_many":\n'
        '    create many users from state.new_users\n'
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context
    initial_state = {
        "new_users": [
            {"id": "user-a", "email": "dup@example.com"},
            {"id": "user-b", "email": "dup@example.com"},
        ]
    }
    result = engine.run_flow(program.flows["bulk_seed"], context, initial_state=initial_state)
    assert result.errors
    rows = engine.frame_registry.query("users")
    assert rows == []


def test_bulk_update_sets_field_for_matching_rows():
    source = (
        'frame is "orders":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "orders"\n'
        'record is "Order":\n'
        '  frame is "orders"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        "    status:\n"
        '      type "string"\n'
        "    archived_at:\n"
        '      type "string"\n'
        'flow is "archive_orders":\n'
        '  step is "seed_one":\n'
        '    kind is "db_create"\n'
        '    record "Order"\n'
        "    values:\n"
        '      id: "order-a"\n'
        '      status: "cancelled"\n'
        '  step is "seed_two":\n'
        '    kind is "db_create"\n'
        '    record "Order"\n'
        "    values:\n"
        '      id: "order-b"\n'
        '      status: "open"\n'
        '  step is "archive_cancelled":\n'
        '    update many orders where:\n'
        '      status is "cancelled"\n'
        '    set:\n'
        '      archived_at: "2024-01-01T00:00:00Z"\n'
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context
    result = engine.run_flow(program.flows["archive_orders"], context, initial_state={})
    assert not result.errors
    rows = engine.frame_registry.query("orders")
    archived = {row["id"]: row.get("archived_at") for row in rows}
    assert archived["order-a"] == "2024-01-01T00:00:00Z"
    assert archived["order-b"] is None


def test_bulk_update_uniqueness_violation_aborts_updates():
    source = (
        'frame is "users":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "users"\n'
        'record is "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        "    email:\n"
        '      type "string"\n'
        '      must be unique\n'
        'flow is "bulk_update":\n'
        '  step is "seed_one":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "user-a"\n'
        '      email: "a@example.com"\n'
        '  step is "seed_two":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "user-b"\n'
        '      email: "b@example.com"\n'
        '  step is "make_duplicates":\n'
        '    update many users where:\n'
        '      id is not null\n'
        '    set:\n'
        '      email: "dup@example.com"\n'
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context
    result = engine.run_flow(program.flows["bulk_update"], context, initial_state={})
    assert result.errors
    rows = engine.frame_registry.query("users")
    emails = {row["id"]: row["email"] for row in rows}
    assert emails["user-a"] == "a@example.com"
    assert emails["user-b"] == "b@example.com"


def test_bulk_delete_removes_matching_rows():
    source = (
        'frame is "users":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "users"\n'
        'record is "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        "    is_active:\n"
        '      type "boolean"\n'
        'flow is "bulk_delete":\n'
        '  step is "seed_active":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "user-a"\n'
        '      is_active: true\n'
        '  step is "seed_inactive":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "user-b"\n'
        '      is_active: false\n'
        '  step is "seed_inactive_two":\n'
        '    kind is "db_create"\n'
        '    record "User"\n'
        "    values:\n"
        '      id: "user-c"\n'
        '      is_active: false\n'
        '  step is "remove_inactive":\n'
        '    delete many users where:\n'
        '      is_active is false\n'
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context
    result = engine.run_flow(program.flows["bulk_delete"], context, initial_state={})
    assert not result.errors
    rows = engine.frame_registry.query("users")
    assert {row["id"] for row in rows} == {"user-a"}


def test_bulk_create_source_must_be_list():
    source = (
        'frame is "users":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "users"\n'
        'record is "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        "    email:\n"
        '      type "string"\n'
        'flow is "bulk_seed":\n'
        '  step is "insert_many":\n'
        '    create many users from state.new_users\n'
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context
    initial_state = {"new_users": {"id": "user-a", "email": "a@example.com"}}
    result = engine.run_flow(program.flows["bulk_seed"], context, initial_state=initial_state)
    assert result.errors
    assert "list" in result.errors[0].error.lower()


def test_parser_requires_from_clause_in_bulk_create():
    source = (
        'frame is "users":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "users"\n'
        'record is "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        'flow is "invalid":\n'
        '  step is "broken":\n'
        '    create many users\n'
    )
    with pytest.raises(ParseError):
        parse_source(source)


def test_parser_requires_where_clause_in_bulk_delete():
    source = (
        'frame is "users":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "users"\n'
        'record is "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        'flow is "invalid":\n'
        '  step is "broken":\n'
        '    delete many users\n'
    )
    with pytest.raises(ParseError):
        parse_source(source)
