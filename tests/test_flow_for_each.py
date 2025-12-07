import pytest

from namel3ss import ast_nodes
from namel3ss.parser import parse_source
from namel3ss.ir import (
    IRAgent,
    IRAiCall,
    IRConditionalBranch,
    IRFlow,
    IRFlowStep,
    IRForEach,
    IRIf,
    IRLet,
    IRModel,
    IRProgram,
    IRSet,
)
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


def test_parse_for_each_variants():
    module = parse_source(
        'flow "f":\n'
        '  step "script":\n'
        '    kind "script"\n'
        '    repeat for each item in items:\n'
        '      set state.last_item be item\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    stmt = next(s for s in flow.steps[0].statements if isinstance(s, ast_nodes.ForEachLoop))
    assert stmt.var_name == "item"
    assert isinstance(stmt.iterable, ast_nodes.Identifier)


def test_parse_for_each_state_and_step_output():
    module = parse_source(
        'flow "f":\n'
        '  step "script":\n'
        '    kind "script"\n'
        '    repeat for each user in state.users:\n'
        '      set state.last_user be user\n'
        '    repeat for each row in step "fetch" output:\n'
        '      set state.last_row be row\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    loops = [s for s in flow.steps[0].statements if isinstance(s, ast_nodes.ForEachLoop)]
    assert len(loops) == 2


def test_runtime_basic_loop():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRLet(name="items", expr=ast_nodes.ListLiteral(items=[ast_nodes.Literal(value=1), ast_nodes.Literal(value=2), ast_nodes.Literal(value=3)])),
                    IRForEach(
                        var_name="item",
                        iterable=ast_nodes.Identifier(name="items"),
                        body=[IRSet(name="state.last_item", expr=ast_nodes.Identifier(name="item"))],
                    ),
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.get("last_item") == 3


def test_runtime_empty_iterable():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRLet(name="items", expr=ast_nodes.ListLiteral(items=[])),
                    IRForEach(
                        var_name="item",
                        iterable=ast_nodes.Identifier(name="items"),
                        body=[IRSet(name="state.last_item", expr=ast_nodes.Identifier(name="item"))],
                    ),
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.get("last_item") is None


def test_runtime_loop_with_if():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRLet(name="scores", expr=ast_nodes.ListLiteral(items=[ast_nodes.Literal(value=40), ast_nodes.Literal(value=60)])),
                    IRForEach(
                        var_name="s",
                        iterable=ast_nodes.Identifier(name="scores"),
                        body=[
                            IRIf(
                                branches=[
                                    IRConditionalBranch(
                                        condition=ast_nodes.BinaryOp(
                                            left=ast_nodes.Identifier(name="s"),
                                            op=">=",
                                            right=ast_nodes.Literal(value=50),
                                        ),
                                        actions=[IRSet(name="state.has_pass", expr=ast_nodes.Literal(value=True))],
                                    )
                                ]
                            )
                        ],
                    ),
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.get("has_pass") is True


def test_runtime_non_list_errors():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRLet(name="x", expr=ast_nodes.Literal(value=123)),
                    IRForEach(
                        var_name="item",
                        iterable=ast_nodes.Identifier(name="x"),
                        body=[IRSet(name="state.last_item", expr=ast_nodes.Identifier(name="item"))],
                    ),
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.errors or result.state.errors
