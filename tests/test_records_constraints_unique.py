import pytest

from namel3ss import ast_nodes
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.errors import IRError
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import IRFlow, IRFlowStep, IRFrame, IRModel, IRProgram, IRRecord, IRRecordField, IRAgent, ast_to_ir
from namel3ss.metrics.tracker import MetricsTracker
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


def _literal_dict(**values):
    return {key: ast_nodes.Literal(value=value) for key, value in values.items()}


def _build_program_with_record(record: IRRecord) -> IRProgram:
    frame_name = record.frame
    return IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        frames={frame_name: IRFrame(name=frame_name, backend="memory", table=frame_name)},
        records={record.name: record},
    )


def _global_unique_record() -> IRRecord:
    fields = {
        "id": IRRecordField(name="id", type="string", primary_key=True, required=True),
        "email": IRRecordField(name="email", type="string", required=True, is_unique=True),
        "name": IRRecordField(name="name", type="string"),
    }
    return IRRecord(name="User", frame="users", fields=fields, primary_key="id")


def _scoped_unique_record(scope_required: bool = True) -> IRRecord:
    fields = {
        "id": IRRecordField(name="id", type="string", primary_key=True, required=True),
        "tenant_id": IRRecordField(name="tenant_id", type="string", required=scope_required),
        "slug": IRRecordField(
            name="slug",
            type="string",
            required=True,
            is_unique=True,
            unique_scope="Tenant",
            unique_scope_field="tenant_id",
        ),
    }
    return IRRecord(name="User", frame="users", fields=fields, primary_key="id")


def _create_flow(record_name: str, values: dict[str, ast_nodes.Expr]) -> IRFlow:
    return IRFlow(
        name=f"create_{values['id'].value}",
        description=None,
        steps=[
            IRFlowStep(
                name="create",
                kind="db_create",
                target=record_name,
                params={"values": values},
            )
        ],
    )


def _update_flow(record_name: str, pk_field: str, pk_value: str, updates: dict[str, ast_nodes.Expr]) -> IRFlow:
    return IRFlow(
        name=f"update_{pk_value}",
        description=None,
        steps=[
            IRFlowStep(
                name="update",
                kind="db_update",
                target=record_name,
                params={
                    "by_id": _literal_dict(**{pk_field: pk_value}),
                    "set": updates,
                },
            )
        ],
    )


def test_global_unique_create_success():
    record = _global_unique_record()
    program = _build_program_with_record(record)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context

    flow_one = _create_flow(
        record.name,
        _literal_dict(id="user-1", email="first@example.com", name="One"),
    )
    flow_two = _create_flow(
        record.name,
        _literal_dict(id="user-2", email="second@example.com", name="Two"),
    )

    result_one = engine.run_flow(flow_one, context, initial_state={})
    result_two = engine.run_flow(flow_two, context, initial_state={})

    assert not result_one.errors
    assert not result_two.errors


def test_global_unique_create_violation():
    record = _global_unique_record()
    program = _build_program_with_record(record)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context

    ok_flow = _create_flow(
        record.name,
        _literal_dict(id="user-1", email="dupe@example.com", name="One"),
    )
    dup_flow = _create_flow(
        record.name,
        _literal_dict(id="user-2", email="dupe@example.com", name="Two"),
    )

    assert not engine.run_flow(ok_flow, context, initial_state={}).errors
    duplicate_result = engine.run_flow(dup_flow, context, initial_state={})

    assert duplicate_result.errors
    assert "unique email" in duplicate_result.errors[0].error.lower()


def test_global_unique_update_violation():
    record = _global_unique_record()
    program = _build_program_with_record(record)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context

    create_one = _create_flow(
        record.name,
        _literal_dict(id="user-1", email="alpha@example.com", name="Alpha"),
    )
    create_two = _create_flow(
        record.name,
        _literal_dict(id="user-2", email="bravo@example.com", name="Bravo"),
    )

    assert not engine.run_flow(create_one, context, initial_state={}).errors
    assert not engine.run_flow(create_two, context, initial_state={}).errors

    update_conflict = _update_flow(
        record.name,
        record.primary_key,
        "user-2",
        _literal_dict(email="alpha@example.com"),
    )
    result = engine.run_flow(update_conflict, context, initial_state={})
    assert result.errors
    assert "unique email" in result.errors[0].error.lower()


def test_scoped_unique_create_success():
    record = _scoped_unique_record()
    program = _build_program_with_record(record)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context

    flows = [
        _create_flow(record.name, _literal_dict(id="user-1", tenant_id="tenant-a", slug="marketing")),
        _create_flow(record.name, _literal_dict(id="user-2", tenant_id="tenant-b", slug="marketing")),
        _create_flow(record.name, _literal_dict(id="user-3", tenant_id="tenant-a", slug="sales")),
    ]
    for flow in flows:
        result = engine.run_flow(flow, context, initial_state={})
        assert not result.errors


def test_scoped_unique_create_violation():
    record = _scoped_unique_record()
    program = _build_program_with_record(record)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context

    first = _create_flow(record.name, _literal_dict(id="user-1", tenant_id="tenant-a", slug="marketing"))
    conflict = _create_flow(record.name, _literal_dict(id="user-2", tenant_id="tenant-a", slug="marketing"))

    assert not engine.run_flow(first, context, initial_state={}).errors
    result = engine.run_flow(conflict, context, initial_state={})
    assert result.errors
    assert "within" in result.errors[0].error.lower()
    assert "tenant" in result.errors[0].error.lower()


def test_scoped_unique_update_violation():
    record = _scoped_unique_record()
    program = _build_program_with_record(record)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context

    create_one = _create_flow(record.name, _literal_dict(id="user-1", tenant_id="tenant-a", slug="marketing"))
    create_two = _create_flow(record.name, _literal_dict(id="user-2", tenant_id="tenant-a", slug="sales"))
    assert not engine.run_flow(create_one, context, initial_state={}).errors
    assert not engine.run_flow(create_two, context, initial_state={}).errors

    update_conflict = _update_flow(
        record.name,
        record.primary_key,
        "user-2",
        _literal_dict(slug="marketing"),
    )
    result = engine.run_flow(update_conflict, context, initial_state={})
    assert result.errors
    assert "within" in result.errors[0].error.lower()


def test_scoped_unique_missing_scope_configuration_error():
    frame = ast_nodes.FrameDecl(name="users", backend="memory", table="users")
    record = ast_nodes.RecordDecl(
        name="User",
        frame="users",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="uuid", primary_key=True),
            ast_nodes.RecordFieldDecl(name="slug", type="string", is_unique=True, unique_scope="Tenant"),
        ],
    )
    module = ast_nodes.Module(declarations=[frame, record])
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "scope field" in str(exc.value)


def test_scoped_unique_missing_scope_value_runtime_error():
    record = _scoped_unique_record(scope_required=False)
    program = _build_program_with_record(record)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context

    missing_scope_flow = _create_flow(
        record.name,
        _literal_dict(id="user-1", slug="marketing"),
    )
    result = engine.run_flow(missing_scope_flow, context, initial_state={})
    assert result.errors
    assert "tenant_id" in result.errors[0].error
