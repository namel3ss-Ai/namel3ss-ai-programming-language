from namel3ss import ast_nodes
import importlib
import sys
import types
from pathlib import Path

from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ir import IRFlow, IRFlowStep, IRLet, IRProgram
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def _make_engine(flow: IRFlow):
    if "namel3ss.flows" not in sys.modules or not isinstance(sys.modules.get("namel3ss.flows"), types.ModuleType):
        flows_pkg = types.ModuleType("namel3ss.flows")
        flows_pkg.__path__ = [str(Path(__file__).resolve().parent.parent / "src" / "namel3ss" / "flows")]
        sys.modules["namel3ss.flows"] = flows_pkg
    FlowEngine = importlib.import_module("namel3ss.flows.engine").FlowEngine
    program = IRProgram(models={}, agents={}, flows={flow.name: flow})
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
    ctx = ExecutionContext(app_name="test", request_id="req-constants", tool_registry=tool_registry, metrics=metrics)
    return engine, ctx


def _build_script_flow(name: str, statements: list) -> IRFlow:
    step = IRFlowStep(name="script", kind="script", target="script", statements=statements)
    return IRFlow(name=name, description=None, steps=[step])


def test_constant_binding_and_usage():
    stmts = [
        IRLet(name="tax_rate", expr=ast_nodes.Literal(value=0.21), is_constant=True),
        IRLet(
            name="total",
            expr=ast_nodes.BinaryOp(
                left=ast_nodes.Literal(value=100),
                op="*",
                right=ast_nodes.Identifier(name="tax_rate"),
            ),
        ),
    ]
    flow = _build_script_flow("constants", stmts)
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.state
    assert result.errors == []
    assert result.state.data.get("tax_rate") == 0.21
    assert result.state.data.get("total") == 21.0


def test_constant_rebind_raises_error():
    stmts = [
        IRLet(name="tax_rate", expr=ast_nodes.Literal(value=0.21), is_constant=True),
        IRLet(name="tax_rate", expr=ast_nodes.Literal(value=0.18)),
    ]
    flow = _build_script_flow("constants_error", stmts)
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors
    assert any("constant" in err.error and "tax_rate" in err.error for err in result.errors)


def test_record_destructuring_success():
    pattern = ast_nodes.DestructuringPattern(
        kind="record",
        fields=[
            ast_nodes.DestructuringField(name="name"),
            ast_nodes.DestructuringField(name="email", alias="user_email"),
        ],
    )
    record_value = {"name": "Ada", "email": "ada@example.com"}
    stmts = [IRLet(name="user", expr=ast_nodes.Literal(value=record_value), pattern=pattern)]
    flow = _build_script_flow("record_destructuring", stmts)
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert result.state
    assert result.state.data.get("name") == "Ada"
    assert result.state.data.get("user_email") == "ada@example.com"


def test_record_destructuring_missing_field_errors():
    pattern = ast_nodes.DestructuringPattern(
        kind="record",
        fields=[ast_nodes.DestructuringField(name="name"), ast_nodes.DestructuringField(name="email")],
    )
    record_value = {"name": "Ada"}
    stmts = [IRLet(name="user", expr=ast_nodes.Literal(value=record_value), pattern=pattern)]
    flow = _build_script_flow("record_destructuring_error", stmts)
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors
    assert any("email" in err.error for err in result.errors)


def test_list_destructuring_success():
    pattern = ast_nodes.DestructuringPattern(kind="list", fields=["first_user", "second_user"])
    stmts = [IRLet(name="users", expr=ast_nodes.Literal(value=["a", "b"]), pattern=pattern)]
    flow = _build_script_flow("list_destructuring", stmts)
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors == []
    assert result.state
    assert result.state.data.get("first_user") == "a"
    assert result.state.data.get("second_user") == "b"


def test_list_destructuring_too_short_errors():
    pattern = ast_nodes.DestructuringPattern(kind="list", fields=["first", "second"])
    stmts = [IRLet(name="users", expr=ast_nodes.Literal(value=["only-one"]), pattern=pattern)]
    flow = _build_script_flow("list_destructuring_error", stmts)
    engine, ctx = _make_engine(flow)
    result = engine.run_flow(flow, ctx)
    assert result.errors
    assert any("list into [first, second]" in err.error for err in result.errors)
