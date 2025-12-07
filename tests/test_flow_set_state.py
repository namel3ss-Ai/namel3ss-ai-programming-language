import pytest

from namel3ss import ast_nodes
from namel3ss.ir import IRFlow, IRFlowStep, IRProgram, IRSet, IRLet, IRAiCall, IRModel, IRAgent
from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.graph import flow_ir_to_graph, FlowState
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.tools.registry import ToolRegistry
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext
from namel3ss.parser import parse_source


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


def test_parse_set_variants():
    module = parse_source(
        'flow "f":\n'
        '  step "script":\n'
        '    kind "script"\n'
        '    set state.answer = 1\n'
        '    set state.answer be state.answer\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    stmts = flow.steps[0].statements
    assert any(isinstance(s, ast_nodes.SetStatement) and s.name == "state.answer" for s in stmts)


def test_runtime_set_simple():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(name="script", kind="script", target="script", statements=[
                IRLet(name="a", expr=ast_nodes.Literal(value=1)),
                IRSet(name="state.answer", expr=ast_nodes.Identifier(name="a")),
            ])
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.get("answer") == 1
    assert result.state.get("state.answer") == 1


def test_runtime_set_with_be():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(name="script", kind="script", target="script", statements=[
                IRLet(name="msg", expr=ast_nodes.Literal(value="hello")),
                IRSet(name="state.greeting", expr=ast_nodes.Identifier(name="msg")),
            ])
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.get("greeting") == "hello"


def test_runtime_set_from_step_output():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(name="script", kind="script", target="script", statements=[
                IRSet(name="state.answer", expr=ast_nodes.Identifier(name="step.ask.output")),
            ]),
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={"step.ask.output": {"text": "hi"}})
    assert result.state.get("answer") == {"text": "hi"}


def test_invalid_set_target_errors():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(name="script", kind="script", target="script", statements=[
                IRSet(name="foo", expr=ast_nodes.Literal(value=1)),
            ]),
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.errors or result.state.errors
