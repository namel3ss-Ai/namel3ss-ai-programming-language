from __future__ import annotations

from namel3ss import ast_nodes
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import (
    IRAgent,
    IRAction,
    IRConditionalBranch,
    IRFlow,
    IRFlowLoop,
    IRFlowStep,
    IRForEach,
    IRIf,
    IRLet,
    IRModel,
    IRProgram,
    IRRepeatUpTo,
    IRRetry,
    IRSet,
)
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolConfig, ToolRegistry


def _script_step(name: str, statements: list) -> IRFlowStep:
    return IRFlowStep(name=name, kind="script", target="script", statements=statements)


def _build_engine(flow: IRFlow) -> tuple[FlowEngine, ExecutionContext, ToolRegistry]:
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        flows={flow.name: flow},
    )
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    tool_registry = ToolRegistry()
    router = ModelRouter(registry)
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    engine = FlowEngine(
        program=program,
        model_registry=registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
    )
    context = ExecutionContext(
        app_name="test-app",
        request_id="req-runtime",
        tracer=None,
        tool_registry=tool_registry,
        metrics=None,
    )
    return engine, context, tool_registry


def _register_flaky_tool(tool_registry: ToolRegistry, fail_times: int, name: str = "flaky"):
    class FlakyTool:
        def __init__(self, failures: int) -> None:
            self.failures = failures
            self.calls: list[dict] = []

        def execute(self, args: dict) -> dict:
            self.calls.append(args)
            if len(self.calls) <= self.failures:
                return {"error": f"fail-{len(self.calls)}"}
            return {"ok": True}

    tool = FlakyTool(fail_times)
    cfg = ToolConfig(name=name, kind="custom", method="POST")
    cfg.execute = tool.execute  # type: ignore[attr-defined]
    tool_registry.register(cfg)
    return tool


def test_repeat_for_each_over_list():
    flow = IRFlow(
        name="foreach_list",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRLet(
                        name="items",
                        expr=ast_nodes.ListLiteral(items=[ast_nodes.Literal(value=1), ast_nodes.Literal(value=2), ast_nodes.Literal(value=3)]),
                    ),
                    IRLet(name="total", expr=ast_nodes.Literal(value=0)),
                    IRForEach(
                        var_name="item",
                        iterable=ast_nodes.Identifier(name="items"),
                        body=[
                            IRSet(
                                name="total",
                                expr=ast_nodes.BinaryOp(left=ast_nodes.Identifier(name="total"), op="+", right=ast_nodes.Identifier(name="item")),
                            )
                        ],
                    ),
                ],
            )
        ],
    )
    engine, ctx, _ = _build_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.state.get("total") == 6
    assert "item" not in result.state.data


def test_repeat_for_each_treats_none_as_empty():
    flow = IRFlow(
        name="foreach_none",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRLet(name="items", expr=ast_nodes.Literal(value=None)),
                    IRLet(name="total", expr=ast_nodes.Literal(value=0)),
                    IRForEach(
                        var_name="item",
                        iterable=ast_nodes.Identifier(name="items"),
                        body=[
                            IRSet(
                                name="total",
                                expr=ast_nodes.BinaryOp(left=ast_nodes.Identifier(name="total"), op="+", right=ast_nodes.Identifier(name="item")),
                            )
                        ],
                    ),
                ],
            )
        ],
    )
    engine, ctx, _ = _build_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.state.get("total") == 0
    assert "item" not in result.state.data
    assert not result.errors


def test_repeat_for_each_wrong_type_errors():
    flow = IRFlow(
        name="foreach_bad",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRLet(name="items", expr=ast_nodes.Literal(value=9)),
                    IRForEach(
                        var_name="item",
                        iterable=ast_nodes.Identifier(name="items"),
                        body=[IRSet(name="state.total", expr=ast_nodes.Identifier(name="item"))],
                    ),
                ],
            )
        ],
    )
    engine, ctx, _ = _build_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors
    assert (
        result.errors[0].error
        == "repeat for each expects a list, but I got 9 instead.\nMake sure the expression after in evaluates to a list of items."
    )


def test_repeat_up_to_counts_and_zero():
    flow = IRFlow(
        name="repeat_counts",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRLet(name="count", expr=ast_nodes.Literal(value=0)),
                    IRRepeatUpTo(
                        count=ast_nodes.Identifier(name="count"),
                        body=[
                            IRSet(
                                name="count",
                                expr=ast_nodes.BinaryOp(left=ast_nodes.Identifier(name="count"), op="+", right=ast_nodes.Literal(value=1)),
                            )
                        ],
                    ),
                    IRSet(name="state.zero_result", expr=ast_nodes.Identifier(name="count")),
                    IRLet(name="limit", expr=ast_nodes.Literal(value=3)),
                    IRRepeatUpTo(
                        count=ast_nodes.Identifier(name="limit"),
                        body=[
                            IRSet(
                                name="count",
                                expr=ast_nodes.BinaryOp(left=ast_nodes.Identifier(name="count"), op="+", right=ast_nodes.Literal(value=1)),
                            )
                        ],
                    ),
                    IRSet(name="state.final_count", expr=ast_nodes.Identifier(name="count")),
                ],
            )
        ],
    )
    engine, ctx, _ = _build_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.state.get("zero_result") == 0
    assert result.state.get("final_count") == 3


def test_repeat_up_to_invalid_counts_error():
    negative_flow = IRFlow(
        name="repeat_negative",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRRepeatUpTo(
                        count=ast_nodes.Literal(value=-1),
                        body=[IRSet(name="state.total", expr=ast_nodes.Literal(value=1))],
                    )
                ],
            )
        ],
    )
    engine, ctx, _ = _build_engine(negative_flow)
    negative_result = engine.run_flow(negative_flow, ctx)
    assert negative_result.errors
    assert (
        negative_result.errors[0].error
        == "repeat up to expects a non-negative number of times, but I got -1 instead."
    )

    type_flow = IRFlow(
        name="repeat_type_error",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRRepeatUpTo(
                        count=ast_nodes.Literal(value="nope"),
                        body=[IRSet(name="state.total", expr=ast_nodes.Literal(value=1))],
                    )
                ],
            )
        ],
    )
    engine2, ctx2, _ = _build_engine(type_flow)
    type_result = engine2.run_flow(type_flow, ctx2)
    assert type_result.errors
    assert (
        type_result.errors[0].error
        == "repeat up to expects a non-negative number of times, but I got 'nope' instead."
    )


def test_flow_level_for_each_over_state_items():
    loop = IRFlowLoop(
        name="loop",
        var_name="item",
        iterable=ast_nodes.Identifier(name="state.items"),
        body=[
            _script_step(
                "process",
                [IRSet(name="state.last", expr=ast_nodes.Identifier(name="item"))],
            )
        ],
    )
    flow = IRFlow(
        name="flow_loop",
        description=None,
        steps=[
            _script_step(
                "init",
                [IRSet(name="state.items", expr=ast_nodes.ListLiteral(items=[ast_nodes.Literal(value=1), ast_nodes.Literal(value=2), ast_nodes.Literal(value=3)]))],
            ),
            loop,
        ],
    )
    engine, ctx, _ = _build_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert not result.errors
    assert result.state.get("last") == 3
    assert "item" not in result.state.data


def test_flow_level_for_each_empty_and_invalid():
    empty_loop = IRFlowLoop(
        name="loop_empty",
        var_name="item",
        iterable=ast_nodes.Identifier(name="state.items"),
        body=[_script_step("process", [IRSet(name="state.seen", expr=ast_nodes.Identifier(name="item"))])],
    )
    empty_flow = IRFlow(
        name="flow_empty",
        description=None,
        steps=[
            _script_step("init", [IRSet(name="state.items", expr=ast_nodes.ListLiteral(items=[]))]),
            empty_loop,
        ],
    )
    engine, ctx, _ = _build_engine(empty_flow)
    result = engine.run_flow(empty_flow, ctx)
    assert not result.errors
    assert "seen" not in result.state.data

    invalid_loop = IRFlowLoop(
        name="loop_invalid",
        var_name="item",
        iterable=ast_nodes.Identifier(name="state.items"),
        body=[_script_step("process", [IRSet(name="state.seen", expr=ast_nodes.Identifier(name="item"))])],
    )
    invalid_flow = IRFlow(
        name="flow_invalid",
        description=None,
        steps=[
            _script_step("init", [IRSet(name="state.items", expr=ast_nodes.Literal(value=7))]),
            invalid_loop,
        ],
    )
    engine2, ctx2, _ = _build_engine(invalid_flow)
    bad = engine2.run_flow(invalid_flow, ctx2)
    assert bad.errors
    assert bad.errors[0].error == "This for each loop expects a list, but I got 7 instead."


def test_retry_succeeds_after_failures():
    flow = IRFlow(
        name="retry_flow",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRRetry(
                        count=ast_nodes.Literal(value=3),
                        with_backoff=False,
                        body=[IRAction(kind="tool", target="flaky", message=None, args={})],
                    )
                ],
            )
        ],
    )
    engine, ctx, tools = _build_engine(flow)
    flaky = _register_flaky_tool(tools, fail_times=2)
    result = engine.run_flow(flow, ctx)
    assert not result.errors
    assert len(flaky.calls) == 3
    assert result.state.get("last_output") == {"ok": True}


def test_retry_with_backoff_respects_attempts():
    flow = IRFlow(
        name="retry_backoff",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRRetry(
                        count=ast_nodes.Literal(value=2),
                        with_backoff=True,
                        body=[IRAction(kind="tool", target="wobbly", message=None, args={})],
                    )
                ],
            )
        ],
    )
    engine, ctx, tools = _build_engine(flow)
    flaky = _register_flaky_tool(tools, fail_times=1, name="wobbly")
    result = engine.run_flow(flow, ctx)
    assert not result.errors
    assert len(flaky.calls) == 2


def test_retry_failure_hits_on_error():
    flow = IRFlow(
        name="retry_failure",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRRetry(
                        count=ast_nodes.Literal(value=2),
                        with_backoff=False,
                        body=[IRAction(kind="tool", target="broken", message=None, args={})],
                    )
                ],
            )
        ],
        error_steps=[
            _script_step("handler", [IRSet(name="state.handled", expr=ast_nodes.Literal(value=True))])
        ],
    )
    engine, ctx, tools = _build_engine(flow)
    flaky = _register_flaky_tool(tools, fail_times=5, name="broken")
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert result.state.get("handled") is True
    assert len(flaky.calls) == 2


def test_loop_error_triggers_on_error_handler():
    loop_body = [
        IRSet(
            name="total",
            expr=ast_nodes.BinaryOp(left=ast_nodes.Identifier(name="total"), op="+", right=ast_nodes.Identifier(name="item")),
        ),
        IRIf(
            branches=[
                IRConditionalBranch(
                    condition=ast_nodes.BinaryOp(left=ast_nodes.Identifier(name="item"), op=">", right=ast_nodes.Literal(value=1)),
                    actions=[IRSet(name="state.fail", expr=ast_nodes.Identifier(name="missing"))],
                )
            ]
        ),
    ]
    flow = IRFlow(
        name="loop_on_error",
        description=None,
        steps=[
            _script_step(
                "script",
                [
                    IRLet(name="items", expr=ast_nodes.ListLiteral(items=[ast_nodes.Literal(value=1), ast_nodes.Literal(value=2), ast_nodes.Literal(value=3)])),
                    IRLet(name="total", expr=ast_nodes.Literal(value=0)),
                    IRForEach(var_name="item", iterable=ast_nodes.Identifier(name="items"), body=loop_body),
                ],
            )
        ],
        error_steps=[
            _script_step("handle", [IRSet(name="state.handled", expr=ast_nodes.Literal(value=True))])
        ],
    )
    engine, ctx, _ = _build_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert result.state.get("handled") is True
    assert result.state.get("total") == 3
