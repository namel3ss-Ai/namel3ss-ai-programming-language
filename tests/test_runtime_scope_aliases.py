import importlib
import sys
import types
from pathlib import Path

from namel3ss import ast_nodes
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ir import IRFlow, IRFlowStep, IRForEach, IRLet, IRModel, IRProgram, IRSet
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def _make_engine(flow: IRFlow):
    if "namel3ss.flows" not in sys.modules or not isinstance(sys.modules.get("namel3ss.flows"), types.ModuleType):
        flows_pkg = types.ModuleType("namel3ss.flows")
        flows_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "src" / "namel3ss" / "flows")]
        sys.modules["namel3ss.flows"] = flows_pkg
    FlowEngine = importlib.import_module("namel3ss.flows.engine").FlowEngine
    program = IRProgram(models={"default": IRModel(name="default")}, agents={}, flows={flow.name: flow})
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
    ctx = ExecutionContext(app_name="test", request_id="req-scope", tool_registry=tool_registry, metrics=metrics)
    return engine, ctx


def _script_flow(name: str, statements: list) -> IRFlow:
    step = IRFlowStep(name="script", kind="script", target="script", statements=statements)
    return IRFlow(name=name, description=None, steps=[step])


def test_bare_identifier_requires_local():
    stmts = [
        IRLet(name="total", expr=ast_nodes.BinaryOp(left=ast_nodes.Identifier(name="base"), op="+", right=ast_nodes.Literal(value=1))),
    ]
    flow = _script_flow("bare_missing", stmts)
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors
    assert any("let base be" in err.error or "I don't know what base" in err.error for err in result.errors)


def test_bare_identifier_resolves_local():
    stmts = [
        IRLet(name="base", expr=ast_nodes.Literal(value=2)),
        IRLet(name="total", expr=ast_nodes.BinaryOp(left=ast_nodes.Identifier(name="base"), op="*", right=ast_nodes.Literal(value=3))),
    ]
    flow = _script_flow("bare_ok", stmts)
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert not result.errors
    assert result.state and result.state.data.get("total") == 6


def test_step_alias_happy_path():
    load_step = IRFlowStep(
        name="load_user",
        alias="user",
        kind="script",
        target="script",
        statements=[IRLet(name="payload", expr=ast_nodes.Literal(value={"email": "user@example.com"}))],
    )
    read_step = IRFlowStep(
        name="use_alias",
        kind="script",
        target="script",
        statements=[IRLet(name="email", expr=ast_nodes.Identifier(name="user.output.email"))],
    )
    flow = IRFlow(name="alias_flow", description=None, steps=[load_step, read_step])
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert not result.errors
    assert result.state and result.state.data.get("email") == "user@example.com"


def test_step_alias_before_run_errors():
    read_step = IRFlowStep(
        name="use_alias",
        kind="script",
        target="script",
        statements=[IRLet(name="email", expr=ast_nodes.Identifier(name="user.output.email"))],
    )
    load_step = IRFlowStep(
        name="load_user",
        alias="user",
        kind="script",
        target="script",
        statements=[IRLet(name="payload", expr=ast_nodes.Literal(value={"email": "user@example.com"}))],
    )
    flow = IRFlow(name="alias_order", description=None, steps=[read_step, load_step])
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors
    assert any("hasn't run yet" in err.error for err in result.errors)


def test_unknown_step_alias_errors():
    stmts = [IRLet(name="email", expr=ast_nodes.Identifier(name="profile.output.email"))]
    flow = _script_flow("alias_unknown", stmts)
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors
    assert any("step alias called profile" in err.error for err in result.errors)


def test_loop_variable_scoping():
    loop = IRForEach(
        var_name="item",
        iterable=ast_nodes.Literal(value=[1, 2]),
        body=[
            IRSet(name="doubled", expr=ast_nodes.BinaryOp(left=ast_nodes.Identifier(name="item"), op="*", right=ast_nodes.Literal(value=2))),
        ],
    )
    after_loop = IRLet(name="outside", expr=ast_nodes.Identifier(name="item"))
    step = IRFlowStep(
        name="script",
        kind="script",
        target="script",
        statements=[
            IRLet(name="doubled", expr=ast_nodes.Literal(value=0)),
            loop,
            after_loop,
        ],
    )
    flow = IRFlow(name="loop_scope", description=None, steps=[step])
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors
    assert any(
        "only inside this loop" in err.error
        or "I don't know what item" in err.error
        or "step alias called item" in err.error
        or "let item be" in err.error
        for err in result.errors
    )
