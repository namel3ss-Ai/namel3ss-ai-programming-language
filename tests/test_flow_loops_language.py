import pytest

from namel3ss import ast_nodes
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.errors import ParseError
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import IRAgent, IRFlow, IRFlowLoop, IRFlowStep, IRModel, IRProgram, IRSet
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.parser import parse_source
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def _build_engine() -> tuple[FlowEngine, ExecutionContext]:
    program = IRProgram(models={"default": IRModel(name="default")}, agents={"helper": IRAgent(name="helper")})
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tools = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tools, router)
    metrics = MetricsTracker()
    engine = FlowEngine(
        program=program,
        model_registry=registry,
        tool_registry=tools,
        agent_runner=agent_runner,
        router=router,
        metrics=metrics,
    )
    ctx = ExecutionContext(app_name="test", request_id="req", tracer=None, tool_registry=tools, metrics=metrics)
    return engine, ctx


def _names_append_step(var_name: str, target_field: str) -> IRFlowStep:
    return IRFlowStep(
        name="add_name",
        kind="script",
        target="add_name",
        statements=[
            IRSet(
                name=target_field,
                expr=ast_nodes.BinaryOp(
                    left=ast_nodes.Identifier(name=target_field),
                    op="+",
                    right=ast_nodes.ListLiteral(
                        items=[
                            ast_nodes.RecordFieldAccess(
                                target=ast_nodes.Identifier(name=var_name),
                                field="name",
                            )
                        ]
                    ),
                ),
            )
        ],
    )


def test_parse_flow_loop_ast():
    module = parse_source(
        'flow is "send_notifications":\n'
        "  for each is recipient in state.recipients:\n"
        '    step is "send":\n'
        '      kind is "ai"\n'
        '      target is "notify_bot"\n'
        '      message is "hello"\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    loop = flow.steps[0]
    assert isinstance(loop, ast_nodes.FlowLoopDecl)
    assert loop.var_name == "recipient"
    iterable = loop.iterable
    if isinstance(iterable, ast_nodes.Identifier):
        assert iterable.name == "state.recipients"
    else:
        assert isinstance(iterable, ast_nodes.RecordFieldAccess)
        assert isinstance(iterable.target, ast_nodes.Identifier)
        assert iterable.target.name == "state"
        assert iterable.field == "recipients"
    assert any(isinstance(step, ast_nodes.FlowStepDecl) and step.name == "send" for step in loop.steps)


def test_parse_flow_loop_invalid_var_name():
    with pytest.raises(ParseError):
        parse_source(
            'flow is "bad_loop":\n'
            "  for each is 123 in state.items:\n"
            '    step is "noop":\n'
            '      kind is "ai"\n'
            '      target is "demo"\n'
        )


def test_flow_loop_runtime_accumulates():
    engine, ctx = _build_engine()
    loop = IRFlowLoop(
        name="for_each_user",
        var_name="user",
        iterable=ast_nodes.Identifier(name="state.users"),
        body=[_names_append_step("user", "state.names")],
    )
    flow = IRFlow(name="collect_names", description=None, steps=[loop])
    initial_state = {"users": [{"name": "Alice"}, {"name": "Bob"}], "names": []}
    result = engine.run_flow(flow, ctx, initial_state=initial_state)
    assert result.state.get("names") == ["Alice", "Bob"]


def test_flow_loop_runtime_empty_iterable():
    engine, ctx = _build_engine()
    loop = IRFlowLoop(
        name="for_each_user",
        var_name="user",
        iterable=ast_nodes.Identifier(name="state.users"),
        body=[_names_append_step("user", "state.names")],
    )
    flow = IRFlow(name="collect_names", description=None, steps=[loop])
    initial_state = {"users": [], "names": []}
    result = engine.run_flow(flow, ctx, initial_state=initial_state)
    assert result.state.get("names") == []
    assert result.errors == []


def test_flow_loop_runtime_non_iterable_error():
    engine, ctx = _build_engine()
    loop = IRFlowLoop(
        name="for_each_user",
        var_name="user",
        iterable=ast_nodes.Identifier(name="state.users"),
        body=[_names_append_step("user", "state.names")],
    )
    flow = IRFlow(name="collect_names", description=None, steps=[loop])
    initial_state = {"users": "not_a_list", "names": []}
    result = engine.run_flow(flow, ctx, initial_state=initial_state)
    assert result.errors
    assert any("list/array-like" in err.error for err in result.errors)


def test_flow_loop_when_condition_filters():
    engine, ctx = _build_engine()
    when_expr = ast_nodes.BinaryOp(
        left=ast_nodes.RecordFieldAccess(target=ast_nodes.Identifier(name="user"), field="active"),
        op="==",
        right=ast_nodes.Literal(value=True),
    )
    step = _names_append_step("user", "state.active_names")
    step.when_expr = when_expr
    loop = IRFlowLoop(
        name="for_each_user",
        var_name="user",
        iterable=ast_nodes.Identifier(name="state.users"),
        body=[step],
    )
    flow = IRFlow(name="collect_active", description=None, steps=[loop])
    initial_state = {
        "users": [{"name": "One", "active": True}, {"name": "Two", "active": False}],
        "active_names": [],
    }
    result = engine.run_flow(flow, ctx, initial_state=initial_state)
    assert result.state.get("active_names") == ["One"]
