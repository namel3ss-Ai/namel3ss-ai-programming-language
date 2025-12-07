import pytest

from namel3ss import ast_nodes
from namel3ss.parser import parse_source
from namel3ss.errors import ParseError
from namel3ss.ir import (
    IRAction,
    IRAgent,
    IRAiCall,
    IRConditionalBranch,
    IRFlow,
    IRFlowStep,
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


def test_parse_if_else_branches():
    module = parse_source(
        'flow "f":\n'
        '  step "script":\n'
        '    kind "script"\n'
        '    if state.ok:\n'
        '      set state.flag be true\n'
        '    else:\n'
        '      set state.flag be false\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    stmt = next(s for s in flow.steps[0].statements if isinstance(s, ast_nodes.IfStatement))
    assert len(stmt.branches) == 2
    assert stmt.branches[1].label == "else"
    assert stmt.branches[1].condition is None


def test_parse_else_without_if_errors():
    with pytest.raises(ParseError):
        parse_source(
            'flow "f":\n'
            '  step "s":\n'
            '    kind "script"\n'
            '    else:\n'
            '      set state.x be 1\n'
        )


def test_runtime_true_branch_sets_state():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRLet(name="value", expr=ast_nodes.Literal(value=10)),
                    IRIf(
                        branches=[
                            IRConditionalBranch(
                                condition=ast_nodes.BinaryOp(
                                    left=ast_nodes.Identifier(name="value"),
                                    op=">",
                                    right=ast_nodes.Literal(value=5),
                                ),
                                actions=[IRSet(name="state.large", expr=ast_nodes.Literal(value=True))],
                            )
                        ]
                    ),
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.get("large") is True


def test_runtime_false_branch_uses_else():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRLet(name="value", expr=ast_nodes.Literal(value=3)),
                    IRIf(
                        branches=[
                            IRConditionalBranch(
                                condition=ast_nodes.BinaryOp(
                                    left=ast_nodes.Identifier(name="value"),
                                    op=">",
                                    right=ast_nodes.Literal(value=5),
                                ),
                                actions=[IRSet(name="state.size", expr=ast_nodes.Literal(value="large"))],
                            ),
                            IRConditionalBranch(
                                condition=None,
                                actions=[IRSet(name="state.size", expr=ast_nodes.Literal(value="small"))],
                                label="else",
                            ),
                        ]
                    ),
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.get("size") == "small"


def test_runtime_condition_uses_state():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRSet(name="state.error", expr=ast_nodes.Literal(value="boom")),
                    IRIf(
                        branches=[
                            IRConditionalBranch(
                                condition=ast_nodes.BinaryOp(
                                    left=ast_nodes.Identifier(name="state.error"),
                                    op="!=",
                                    right=ast_nodes.Literal(value=None),
                                ),
                                actions=[IRSet(name="state.has_error", expr=ast_nodes.Literal(value=True))],
                            )
                        ]
                    ),
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.get("has_error") is True


def test_runtime_bad_condition_errors():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRIf(
                        branches=[
                            IRConditionalBranch(
                                condition=ast_nodes.Identifier(name="missing"),
                                actions=[IRAction(kind="noop", target="noop")],
                            )
                        ]
                    )
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.errors
