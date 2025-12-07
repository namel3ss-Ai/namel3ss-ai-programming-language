import pytest

from namel3ss import ast_nodes
from namel3ss.ir import IRFrame, IRFlow, IRFlowStep, IRModel, IRAgent, IRProgram, ast_to_ir
from namel3ss.parser import parse_source
from namel3ss.flows.engine import FlowEngine
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.tools.registry import ToolRegistry
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext
from namel3ss.errors import Namel3ssError


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
    exec_ctx = ExecutionContext(app_name="test", request_id="req", tracer=None, tool_registry=tool_registry, metrics=metrics)
    runtime_ctx = engine._build_runtime_context(exec_ctx)
    return engine, runtime_ctx


def test_parse_frame_update_delete():
    module = parse_source(
        'frame "users":\n'
        '  backend "memory"\n'
        '  table "users"\n'
        '\n'
        'flow "f":\n'
        '  step "u":\n'
        '    kind "frame_update"\n'
        '    frame "users"\n'
        '    where:\n'
        '      id: 1\n'
        '    set:\n'
        '      name: "Bob"\n'
        '  step "d":\n'
        '    kind "frame_delete"\n'
        '    frame "users"\n'
        '    where:\n'
        '      id: 2\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    upd = flow.steps[0]
    assert isinstance(upd.params.get("set"), dict)
    assert isinstance(upd.params.get("where"), dict)


def test_runtime_update_and_query():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="insert",
                kind="frame_insert",
                target="users",
                params={"values": {"id": ast_nodes.Literal(value=1), "name": ast_nodes.Literal(value="Alice")}},
            ),
            IRFlowStep(
                name="update",
                kind="frame_update",
                target="users",
                params={
                    "where": {"id": ast_nodes.Literal(value=1)},
                    "set": {"name": ast_nodes.Literal(value="Bob")},
                },
            ),
            IRFlowStep(
                name="load",
                kind="frame_query",
                target="users",
                params={"where": {"id": ast_nodes.Literal(value=1)}},
            ),
        ],
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        frames={"users": IRFrame(name="users", backend="memory", table="users")},
    )
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    rows = result.state.get("last_output")
    assert rows and rows[0]["name"] == "Bob"


def test_runtime_delete_and_count_output():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="insert1",
                kind="frame_insert",
                target="users",
                params={"values": {"id": ast_nodes.Literal(value=1), "name": ast_nodes.Literal(value="A")}},
            ),
            IRFlowStep(
                name="insert2",
                kind="frame_insert",
                target="users",
                params={"values": {"id": ast_nodes.Literal(value=2), "name": ast_nodes.Literal(value="B")}},
            ),
            IRFlowStep(
                name="delete",
                kind="frame_delete",
                target="users",
                params={"where": {"id": ast_nodes.Literal(value=1)}},
            ),
            IRFlowStep(
                name="load",
                kind="frame_query",
                target="users",
                params={"where": {"id": ast_nodes.Literal(value=1)}},
            ),
        ],
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        frames={"users": IRFrame(name="users", backend="memory", table="users")},
    )
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    rows = result.state.get("last_output")
    assert rows == []
    # registry store should only contain the row with id 2
    stored = runtime_ctx.frames._store.get("users", [])
    assert len(stored) == 1 and stored[0]["id"] == 2


def test_runtime_invalid_update_missing_set():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(name="update", kind="frame_update", target="users", params={"where": {"id": ast_nodes.Literal(value=1)}}),
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={}, frames={"users": IRFrame(name="users", backend="memory", table="users")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.errors
    assert any("N3L-840" in err.error for err in result.errors)


def test_runtime_invalid_delete_missing_where():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(name="delete", kind="frame_delete", target="users", params={}),
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={}, frames={"users": IRFrame(name="users", backend="memory", table="users")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.errors
    assert any("N3L-841" in err.error for err in result.errors)
