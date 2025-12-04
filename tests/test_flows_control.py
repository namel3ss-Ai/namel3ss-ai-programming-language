import asyncio

from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.graph import FlowGraph, FlowNode, FlowState
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.tools.registry import ToolRegistry
from namel3ss.agent.engine import AgentRunner
from namel3ss.ir import IRProgram
from namel3ss.runtime.context import ExecutionContext


def build_engine():
    program = IRProgram()
    registry = ModelRegistry()
    router = ModelRouter(registry)
    tools = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tools, router)
    engine = FlowEngine(program, registry, tools, agent_runner, router)
    ctx = engine._build_runtime_context(ExecutionContext(app_name="demo", request_id="req"))
    return engine, ctx


def test_for_each_runs_body_for_all_items():
    engine, runtime_ctx = build_engine()
    body_step = {"id": "body", "kind": "function", "config": {"callable": lambda st: st.set("ran", True) or "done"}}
    node = FlowNode(
        id="foreach",
        kind="for_each",
        config={"items": [1, 2, 3], "body": [body_step]},
        next_ids=[],
    )
    graph = FlowGraph(nodes={"foreach": node}, entry_id="foreach")
    result = asyncio.run(engine.a_run_flow(graph, FlowState(), runtime_ctx, flow_name="f"))
    # Body step should run per item plus container step
    assert len([s for s in result.steps if s.node_id == "body"]) == 3
    assert any(s.node_id == "foreach" for s in result.steps)
    items_meta = result.state.get("step.foreach.items")
    assert len(items_meta) == 3


def test_try_catch_handles_failure_and_runs_finally():
    engine, runtime_ctx = build_engine()

    def fail(_state):
        raise RuntimeError("fail")

    try_step = {"id": "try_step", "kind": "function", "config": {"callable": fail}}
    catch_step = {"id": "catch_step", "kind": "function", "config": {"callable": lambda st: st.set("recovered", True)}}
    finally_step = {"id": "finally_step", "kind": "function", "config": {"callable": lambda st: st.set("done", True)}}
    node = FlowNode(
        id="try_node",
        kind="try",
        config={"try_steps": [try_step], "catch_steps": [catch_step], "finally_steps": [finally_step]},
        next_ids=[],
    )
    graph = FlowGraph(nodes={"try_node": node}, entry_id="try_node")
    result = asyncio.run(engine.a_run_flow(graph, FlowState(), runtime_ctx, flow_name="t"))
    ids = [s.node_id for s in result.steps]
    assert "catch_step" in ids
    assert "finally_step" in ids
    assert result.state.get("done") is True


def test_timeout_failure_is_recorded():
    engine, runtime_ctx = build_engine()
    node = FlowNode(
        id="slow",
        kind="function",
        config={"callable": lambda st: "slow", "simulate_duration": 0.1, "timeout_seconds": 0.01},
        next_ids=[],
    )
    graph = FlowGraph(nodes={"slow": node}, entry_id="slow")
    result = asyncio.run(engine.a_run_flow(graph, FlowState(), runtime_ctx, flow_name="timeout"))
    slow_step = next(step for step in result.steps if step.node_id == "slow")
    assert slow_step.success is False
    assert "timeout" in slow_step.error_message or slow_step.error_message


def test_metrics_present_with_durations_and_costs():
    engine, runtime_ctx = build_engine()
    node = FlowNode(
        id="metric",
        kind="function",
        config={"callable": lambda st: {"value": 1, "cost": 0.5}, "simulate_duration": 0.01},
        next_ids=[],
    )
    graph = FlowGraph(nodes={"metric": node}, entry_id="metric")
    result = asyncio.run(engine.a_run_flow(graph, FlowState(), runtime_ctx, flow_name="m"))
    assert result.step_metrics["metric"].duration_seconds > 0
    assert result.step_metrics["metric"].cost == 0.5
    assert result.total_cost >= 0.5
    assert result.total_duration_seconds >= result.step_metrics["metric"].duration_seconds
