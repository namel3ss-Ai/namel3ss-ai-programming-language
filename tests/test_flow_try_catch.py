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
    IRLet,
    IRModel,
    IRProgram,
    IRSet,
    IRIf,
    IRTryCatch,
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


def test_parse_try_catch():
    module = parse_source(
        'flow "f":\n'
        '  step "s":\n'
        '    kind "script"\n'
        '    try:\n'
        '      set state.a be 1\n'
        '    catch err:\n'
        '      set state.error be err.message\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    stmt = next(s for s in flow.steps[0].statements if isinstance(s, ast_nodes.TryCatchStatement))
    assert stmt.error_identifier == "err"
    assert len(stmt.try_block) == 1
    assert len(stmt.catch_block) == 1


def test_parse_invalid_catch_without_name():
    with pytest.raises(ParseError):
        parse_source(
            'flow "f":\n'
            '  step "s":\n'
            '    kind "script"\n'
            '    try:\n'
            '      set state.a be 1\n'
            '    catch:\n'
            '      set state.error be 1\n'
        )


def test_runtime_try_catch_no_error_skips_catch():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRTryCatch(
                        try_body=[IRLet(name="a", expr=ast_nodes.Literal(value=1))],
                        error_name="err",
                        catch_body=[IRSet(name="state.error", expr=ast_nodes.Literal(value=True))],
                    ),
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.get("error") is None


def test_runtime_try_catch_handles_error():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRTryCatch(
                        try_body=[
                            IRSet(name="state.a", expr=ast_nodes.Identifier(name="missing")),
                        ],
                        error_name="err",
                        catch_body=[IRSet(name="state.error_message", expr=ast_nodes.Identifier(name="err.message"))],
                    )
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert "error_message" in result.state.data
    assert result.state.get("error_message")


def test_error_fields_accessible_in_catch():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRTryCatch(
                        try_body=[IRSet(name="state.a", expr=ast_nodes.Identifier(name="missing"))],
                        error_name="err",
                        catch_body=[
                            IRLet(name="msg", expr=ast_nodes.Identifier(name="err.message")),
                            IRSet(name="state.msg", expr=ast_nodes.Identifier(name="msg")),
                        ],
                    )
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.get("msg")


def test_catch_with_conditionals():
    flow = IRFlow(
        name="f",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRTryCatch(
                        try_body=[IRSet(name="state.a", expr=ast_nodes.Identifier(name="missing"))],
                        error_name="err",
                        catch_body=[
                            IRIf(
                                branches=[
                                    IRConditionalBranch(
                                        condition=ast_nodes.BinaryOp(
                                            left=ast_nodes.Identifier(name="err.kind"),
                                            op="==",
                                            right=ast_nodes.Literal(value="Namel3ssError"),
                                        ),
                                        actions=[IRSet(name="state.is_error", expr=ast_nodes.Literal(value=True))],
                                    ),
                                    IRConditionalBranch(
                                        condition=None,
                                        actions=[IRSet(name="state.is_error", expr=ast_nodes.Literal(value=True))],
                                        label="else",
                                    ),
                                ]
                            )
                        ],
                    )
                ],
            )
        ],
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        ai_calls={"bot": IRAiCall(name="bot", model_name="default")},
    )
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
    assert result.state.get("is_error") is True
