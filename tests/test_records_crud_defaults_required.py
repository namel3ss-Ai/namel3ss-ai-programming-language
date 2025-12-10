from datetime import datetime

import pytest

from namel3ss import ast_nodes
from namel3ss.errors import Namel3ssError
from namel3ss.ir import IRFlow, IRFlowStep, IRFrame, IRModel, IRProgram, IRRecord, IRRecordField, IRAgent
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


def test_defaults_resolve_to_runtime_values():
    record = IRRecord(
        name="User",
        frame="users",
        fields={
            "id": IRRecordField(name="id", type="string", primary_key=True, required=True),
            "active": IRRecordField(name="active", type="bool", default=True),
            "score": IRRecordField(name="score", type="float", default=0.5),
            "label": IRRecordField(name="label", type="string", default="guest"),
            "created_at": IRRecordField(name="created_at", type="datetime", default="now"),
        },
        primary_key="id",
    )
    flow = IRFlow(
        name="create_user",
        description=None,
        steps=[
            IRFlowStep(
                name="create",
                kind="db_create",
                target="User",
                params={"values": {"id": ast_nodes.Literal(value="user-1")}},
            )
        ],
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        frames={"users": IRFrame(name="users", backend="memory", table="users")},
        records={"User": record},
    )
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})

    created = result.state.get("step.create.output")
    assert created["active"] is True
    assert created["score"] == 0.5
    assert created["label"] == "guest"
    assert isinstance(created["created_at"], datetime)
    assert not isinstance(created["active"], ast_nodes.Literal)


def test_required_field_missing_raises():
    record = IRRecord(
        name="User",
        frame="users",
        fields={
            "id": IRRecordField(name="id", type="string", primary_key=True, required=True),
            "email": IRRecordField(name="email", type="string", required=True),
        },
        primary_key="id",
    )
    flow = IRFlow(
        name="create_user",
        description=None,
        steps=[
            IRFlowStep(
                name="create",
                kind="db_create",
                target="User",
                params={"values": {"id": ast_nodes.Literal(value="user-1")}},
            )
        ],
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        frames={"users": IRFrame(name="users", backend="memory", table="users")},
        records={"User": record},
    )
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.errors
    assert "N3L-1502" in result.errors[0].error


def test_required_field_with_default_is_used():
    record = IRRecord(
        name="User",
        frame="users",
        fields={
            "id": IRRecordField(name="id", type="string", primary_key=True, required=True),
            "email": IRRecordField(name="email", type="string", required=True, default="unknown@example.com"),
        },
        primary_key="id",
    )
    flow = IRFlow(
        name="create_user",
        description=None,
        steps=[
            IRFlowStep(
                name="create",
                kind="db_create",
                target="User",
                params={"values": {"id": ast_nodes.Literal(value="user-1")}},
            )
        ],
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        frames={"users": IRFrame(name="users", backend="memory", table="users")},
        records={"User": record},
    )
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    created = result.state.get("step.create.output")
    assert created["email"] == "unknown@example.com"
