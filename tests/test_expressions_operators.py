from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import ast_to_ir
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.parser import parse_source
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def _build_engine_from_source(source: str) -> tuple[FlowEngine, ExecutionContext, str]:
    module = parse_source(source)
    program = ast_to_ir(module)
    flow_name = next(iter(program.flows.keys()))
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
    ctx = ExecutionContext(app_name="test", request_id="req-expr", tool_registry=tool_registry, metrics=metrics)
    runtime_ctx = engine._build_runtime_context(ctx)
    return engine, runtime_ctx.execution_context, flow_name


def test_binary_and_unary_minus_plus():
    source = (
        'flow is "calc":\n'
        '  step is "compute":\n'
        "    let a be 10\n"
        "    let b be 3\n"
        "    let diff_symbol be a - b\n"
        "    let diff_word be a minus b\n"
        "    let negative be -a\n"
        "    let positive be +b\n"
        "    let neg_literal be -10\n"
    )
    engine, ctx, flow_name = _build_engine_from_source(source)
    flow = engine.program.flows[flow_name]
    result = engine.run_flow(flow, ctx, initial_state={})
    assert result.errors == []
    state = result.state.data
    assert state.get("diff_symbol") == 7
    assert state.get("diff_word") == 7
    assert state.get("negative") == -10
    assert state.get("positive") == 3
    assert state.get("neg_literal") == -10


def test_empty_string_and_record_literal():
    source = (
        'flow is "records":\n'
        '  step is "make_record":\n'
        '    let empty_str be ""\n'
        '    let user be { name: "Alice", age: 30, active: true }\n'
        "    let name be user.name\n"
    )
    engine, ctx, flow_name = _build_engine_from_source(source)
    flow = engine.program.flows[flow_name]
    result = engine.run_flow(flow, ctx, initial_state={})
    assert result.errors == []
    state = result.state.data
    assert state.get("empty_str") == ""
    assert state.get("user") == {"name": "Alice", "age": 30, "active": True}
    assert state.get("name") == "Alice"


def test_script_step_without_explicit_action():
    source = (
        'flow is "script_only":\n'
        '  step is "compute":\n'
        "    let a be 10\n"
        "    let b be 20\n"
        "    let sum be a + b\n"
    )
    engine, ctx, flow_name = _build_engine_from_source(source)
    flow = engine.program.flows[flow_name]
    result = engine.run_flow(flow, ctx, initial_state={})
    assert result.errors == []
    assert result.state.data.get("sum") == 30
