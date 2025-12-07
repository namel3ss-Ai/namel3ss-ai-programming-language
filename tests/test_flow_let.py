import pytest

from namel3ss import ast_nodes
from namel3ss.ir import IRFlow, IRFlowStep, IRProgram, IRStatement, IRAction, IRLet, IRAiCall, IRModel, IRAgent
from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.graph import flow_ir_to_graph
from namel3ss.flows.graph import FlowState
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


def test_parse_let_variants():
    from namel3ss.parser import parse_source

    module = parse_source(
        'flow "f":\n'
        '  step "one":\n'
        '    kind "ai"\n'
        '    target "bot"\n'
        '  step "two":\n'
        '    kind "script"\n'
        '    let a = 1\n'
        '    let b be a\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    script_step = flow.steps[1]
    assert any(isinstance(s, ast_nodes.LetStatement) and s.name == "a" for s in script_step.statements)
    assert any(isinstance(s, ast_nodes.LetStatement) and s.name == "b" for s in script_step.statements)


def test_runtime_let_literals_and_chain():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(name="script", kind="script", target="script", statements=[
                IRLet(name="a", expr=ast_nodes.Literal(value=1)),
                IRLet(name="b", expr=ast_nodes.Identifier(name="a")),
            ])
        ],
    )
    program = IRProgram(ai_calls={"bot": IRAiCall(name="bot", model_name="default")}, models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.variables.resolve("a") == 1
    assert result.state.variables.resolve("b") == 1


def test_runtime_let_from_step_output():
    # script assigns from prior step output
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(name="script", kind="script", target="script", statements=[
                IRLet(name="answer", expr=ast_nodes.Identifier(name="step.ask.output")),
            ]),
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={"step.ask.output": {"text": "hi"}})
    assert result.state.variables.resolve("answer") == {"text": "hi"}


def test_undefined_step_reference_errors():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(name="script", kind="script", target="script", statements=[
                IRLet(name="x", expr=ast_nodes.Identifier(name="step.nope.output")),
            ]),
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    state = FlowState()
    with pytest.raises(Exception):
        engine.run_flow(flow, runtime_ctx.execution_context, initial_state=state)


def test_undefined_local_reference_errors():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(name="script", kind="script", target="script", statements=[
                IRLet(name="b", expr=ast_nodes.Identifier(name="a")),
            ]),
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    state = FlowState()
    with pytest.raises(Exception):
        engine.run_flow(flow, runtime_ctx.execution_context, initial_state=state)
