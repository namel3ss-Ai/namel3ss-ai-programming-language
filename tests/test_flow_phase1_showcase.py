from namel3ss import ast_nodes
from namel3ss.ir import (
    IRAgent,
    IRConditionalBranch,
    IRFlow,
    IRFlowStep,
    IRForEach,
    IRIf,
    IRLet,
    IRModel,
    IRProgram,
    IRSet,
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


def test_phase1_integration_flow():
    flow = IRFlow(
        name="phase1_integration",
        description=None,
        steps=[
            IRFlowStep(
                name="script",
                kind="script",
                target="script",
                statements=[
                    IRLet(
                        name="scores",
                        expr=ast_nodes.ListLiteral(
                            items=[ast_nodes.Literal(value=40), ast_nodes.Literal(value=60)]
                        ),
                    ),
                    IRSet(name="state.handled_count", expr=ast_nodes.Literal(value=0)),
                    IRSet(name="state.has_pass", expr=ast_nodes.Literal(value=False)),
                    IRForEach(
                        var_name="score",
                        iterable=ast_nodes.Identifier(name="scores"),
                        body=[
                            IRTryCatch(
                                try_body=[
                                    IRIf(
                                        branches=[
                                            IRConditionalBranch(
                                                condition=ast_nodes.BinaryOp(
                                                    left=ast_nodes.Identifier(name="score"),
                                                    op=">=",
                                                    right=ast_nodes.Literal(value=50),
                                                ),
                                                actions=[
                                                    IRSet(
                                                        name="state.has_pass",
                                                        expr=ast_nodes.Literal(value=True),
                                                    )
                                                ],
                                            )
                                        ]
                                    ),
                                    IRSet(
                                        name="state.handled_count",
                                        expr=ast_nodes.BinaryOp(
                                            left=ast_nodes.Identifier(name="state.handled_count"),
                                            op="+",
                                            right=ast_nodes.Literal(value=1),
                                        ),
                                    ),
                                    IRSet(name="state.last_score", expr=ast_nodes.Identifier(name="score")),
                                ],
                                error_name="err",
                                catch_body=[
                                    IRSet(name="state.last_error", expr=ast_nodes.Identifier(name="err.message"))
                                ],
                            )
                        ],
                    ),
                    IRTryCatch(
                        try_body=[IRSet(name="state.final_message", expr=ast_nodes.Identifier(name="missing_var"))],
                        error_name="err",
                        catch_body=[
                            IRSet(name="state.caught", expr=ast_nodes.Identifier(name="err.message")),
                        ],
                    ),
                ],
            )
        ],
    )
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})

    assert result.state.get("handled_count") == 2
    assert result.state.get("has_pass") is True
    assert result.state.get("last_score") == 60
    assert result.state.get("caught")  # error captured
    assert not result.errors  # caught errors should prevent crashes
