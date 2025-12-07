import pytest

from namel3ss import ast_nodes
from namel3ss.parser import parse_source
from namel3ss.ir import IRFlow, IRFlowStep, IRProgram, IRFrame, IRSet, IRLet, IRModel, IRAgent, ast_to_ir, IRError
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


def test_parse_frame_and_steps():
    module = parse_source(
        'frame "conversations":\n'
        '  backend "memory"\n'
        '  table "conversations"\n'
        '\n'
        'flow "log_and_load":\n'
        '  step "store":\n'
        '    kind "frame_insert"\n'
        '    frame "conversations"\n'
        '    values:\n'
        '      message: "hi"\n'
        '  step "load":\n'
        '    kind "frame_query"\n'
        '    frame "conversations"\n'
        '    where:\n'
        '      message: "hi"\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    step = flow.steps[0]
    assert isinstance(step.params.get("values"), dict)


def test_validation_unknown_frame():
    flow = ast_nodes.FlowDecl(
        name="f",
        steps=[
            ast_nodes.FlowStepDecl(
                name="s",
                kind="frame_insert",
                target="missing",
                params={"values": {"message": ast_nodes.Literal(value="hi")}},
            )
        ],
    )
    module = ast_nodes.Module(declarations=[flow])
    with pytest.raises(IRError):
        ast_to_ir(module)


def test_runtime_insert_and_query():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="store",
                kind="frame_insert",
                target="logs",
                params={"values": {"message": ast_nodes.Literal(value="hello")}},
            ),
            IRFlowStep(
                name="load",
                kind="frame_query",
                target="logs",
                params={"where": {}},
            ),
        ],
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        frames={"logs": IRFrame(name="logs", backend="memory", table="logs")},
    )
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert isinstance(result.state.get("last_output"), list)
    assert any(row.get("message") == "hello" for row in result.state.get("last_output"))


def test_runtime_filtered_query():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="a",
                kind="frame_insert",
                target="logs",
                params={"values": {"user_id": ast_nodes.Literal(value=1), "message": ast_nodes.Literal(value="a")}},
            ),
            IRFlowStep(
                name="b",
                kind="frame_insert",
                target="logs",
                params={"values": {"user_id": ast_nodes.Literal(value=2), "message": ast_nodes.Literal(value="b")}},
            ),
            IRFlowStep(
                name="load",
                kind="frame_query",
                target="logs",
                params={"where": {"user_id": ast_nodes.Literal(value=2)}},
            ),
        ],
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        frames={"logs": IRFrame(name="logs", backend="memory", table="logs")},
    )
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    rows = result.state.get("last_output")
    assert rows and rows[0]["user_id"] == 2 and rows[0]["message"] == "b"
