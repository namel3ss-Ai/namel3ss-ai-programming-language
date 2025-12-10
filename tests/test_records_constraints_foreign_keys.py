import pytest

from namel3ss import ast_nodes
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.errors import IRError
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import (
    IRAgent,
    IRFlow,
    IRFlowStep,
    IRFrame,
    IRModel,
    IRProgram,
    IRRecord,
    IRRecordField,
    ast_to_ir,
)
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


def _user_record() -> IRRecord:
    fields = {
        "id": IRRecordField(name="id", type="string", primary_key=True, required=True),
        "email": IRRecordField(name="email", type="string"),
    }
    return IRRecord(name="User", frame="users", fields=fields, primary_key="id")


def _order_record(require_user: bool = True) -> IRRecord:
    fields = {
        "id": IRRecordField(name="id", type="string", primary_key=True, required=True),
        "user_id": IRRecordField(
            name="user_id",
            type="string",
            required=require_user,
            references_record="User",
            reference_target_field="id",
        ),
    }
    return IRRecord(name="Order", frame="orders", fields=fields, primary_key="id")


def _program_with_records(user_record: IRRecord, order_record: IRRecord) -> IRProgram:
    return IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        frames={
            "users": IRFrame(name="users", backend="memory", table="users"),
            "orders": IRFrame(name="orders", backend="memory", table="orders"),
        },
        records={"User": user_record, "Order": order_record},
    )


def _create_flow(record_name: str, values: dict[str, ast_nodes.Expr]) -> IRFlow:
    return IRFlow(
        name=f"create_{record_name.lower()}",
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
        name=f"update_{record_name.lower()}",
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


def test_foreign_key_create_success():
    program = _program_with_records(_user_record(), _order_record())
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context

    create_user = _create_flow("User", _literal_dict(id="user-1", email="one@example.com"))
    create_order = _create_flow("Order", _literal_dict(id="order-1", user_id="user-1"))

    assert not engine.run_flow(create_user, context, initial_state={}).errors
    order_result = engine.run_flow(create_order, context, initial_state={})
    assert not order_result.errors


def test_foreign_key_create_failure():
    program = _program_with_records(_user_record(), _order_record())
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context

    create_order = _create_flow("Order", _literal_dict(id="order-1", user_id="missing"))
    result = engine.run_flow(create_order, context, initial_state={})
    assert result.errors
    assert "does not point to an existing User" in result.errors[0].error


def test_foreign_key_update_failure():
    program = _program_with_records(_user_record(), _order_record())
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context

    create_user = _create_flow("User", _literal_dict(id="user-1", email="one@example.com"))
    create_order = _create_flow("Order", _literal_dict(id="order-1", user_id="user-1"))
    assert not engine.run_flow(create_user, context, initial_state={}).errors
    assert not engine.run_flow(create_order, context, initial_state={}).errors

    update_order = _update_flow("Order", "id", "order-1", _literal_dict(user_id="missing"))
    result = engine.run_flow(update_order, context, initial_state={})
    assert result.errors
    assert "does not point to an existing User" in result.errors[0].error


def test_foreign_key_nullable_field_skips_check():
    program = _program_with_records(_user_record(), _order_record(require_user=False))
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context

    create_order = _create_flow("Order", _literal_dict(id="order-1"))
    result = engine.run_flow(create_order, context, initial_state={})
    assert not result.errors

    create_user = _create_flow("User", _literal_dict(id="user-1", email="one@example.com"))
    assert not engine.run_flow(create_user, context, initial_state={}).errors

    update_order = _update_flow("Order", "id", "order-1", _literal_dict(user_id="user-1"))
    assert not engine.run_flow(update_order, context, initial_state={}).errors


def test_ir_reference_missing_record():
    users_frame = ast_nodes.FrameDecl(name="users", backend="memory", table="users")
    orders_frame = ast_nodes.FrameDecl(name="orders", backend="memory", table="orders")
    order_record = ast_nodes.RecordDecl(
        name="Order",
        frame="orders",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="string", primary_key=True),
            ast_nodes.RecordFieldDecl(name="user_id", type="string", references_record="MissingUser"),
        ],
    )
    module = ast_nodes.Module(declarations=[users_frame, orders_frame, order_record])
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "references \"MissingUser\"" in str(exc.value)


def test_ir_reference_missing_target_field():
    users_frame = ast_nodes.FrameDecl(name="users", backend="memory", table="users")
    orders_frame = ast_nodes.FrameDecl(name="orders", backend="memory", table="orders")
    user_record = ast_nodes.RecordDecl(
        name="User",
        frame="users",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="string", primary_key=True),
        ],
    )
    order_record = ast_nodes.RecordDecl(
        name="Order",
        frame="orders",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="string", primary_key=True),
            ast_nodes.RecordFieldDecl(name="user_id", type="string", references_record="User", references_field="legacy_id"),
        ],
    )
    module = ast_nodes.Module(declarations=[users_frame, orders_frame, user_record, order_record])
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "legacy_id" in str(exc.value)


def test_ir_relationship_missing_via_field():
    users_frame = ast_nodes.FrameDecl(name="users", backend="memory", table="users")
    orders_frame = ast_nodes.FrameDecl(name="orders", backend="memory", table="orders")
    user_record = ast_nodes.RecordDecl(
        name="User",
        frame="users",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="string", primary_key=True),
        ],
    )
    order_record = ast_nodes.RecordDecl(
        name="Order",
        frame="orders",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="string", primary_key=True),
            ast_nodes.RecordFieldDecl(name="user", type="string", relationship_target="User", relationship_via_field="user_id"),
        ],
    )
    module = ast_nodes.Module(declarations=[users_frame, orders_frame, user_record, order_record])
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "can’t find a field named user_id" in str(exc.value)


def test_ir_relationship_requires_foreign_key():
    users_frame = ast_nodes.FrameDecl(name="users", backend="memory", table="users")
    orders_frame = ast_nodes.FrameDecl(name="orders", backend="memory", table="orders")
    user_record = ast_nodes.RecordDecl(
        name="User",
        frame="users",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="string", primary_key=True),
        ],
    )
    order_fields = [
        ast_nodes.RecordFieldDecl(name="id", type="string", primary_key=True),
        ast_nodes.RecordFieldDecl(name="user_id", type="string"),
        ast_nodes.RecordFieldDecl(name="user", type="string", relationship_target="User", relationship_via_field="user_id"),
    ]
    order_record = ast_nodes.RecordDecl(name="Order", frame="orders", fields=order_fields)
    module = ast_nodes.Module(declarations=[users_frame, orders_frame, user_record, order_record])
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "does not reference \"User\"" in str(exc.value)


def test_ir_relationship_valid():
    users_frame = ast_nodes.FrameDecl(name="users", backend="memory", table="users")
    orders_frame = ast_nodes.FrameDecl(name="orders", backend="memory", table="orders")
    user_record = ast_nodes.RecordDecl(
        name="User",
        frame="users",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="string", primary_key=True),
        ],
    )
    order_fields = [
        ast_nodes.RecordFieldDecl(
            name="id",
            type="string",
            primary_key=True,
        ),
        ast_nodes.RecordFieldDecl(
            name="user_id",
            type="string",
            references_record="User",
        ),
        ast_nodes.RecordFieldDecl(
            name="user",
            type="string",
            relationship_target="User",
            relationship_via_field="user_id",
        ),
    ]
    order_record = ast_nodes.RecordDecl(name="Order", frame="orders", fields=order_fields)
    module = ast_nodes.Module(declarations=[users_frame, orders_frame, user_record, order_record])
    program = ast_to_ir(module)
    order_ir = program.records["Order"]
    assert "user" in order_ir.relationships
    relationship = order_ir.relationships["user"]
    assert relationship.target_record == "User"
    assert relationship.via_field == "user_id"
