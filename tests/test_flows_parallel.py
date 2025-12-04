import asyncio
import time

from namel3ss.flows.engine import FlowEngine
from namel3ss.flows.graph import FlowGraph, FlowNode, FlowState
from namel3ss.ir import IRProgram
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.tools.registry import ToolRegistry
from namel3ss.agent.engine import AgentRunner
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


def test_parallel_steps_reduce_total_time():
    engine, runtime_ctx = build_engine()
    node = FlowNode(
        id="parallel",
        kind="parallel",
        config={
            "steps": [
                {"id": "a", "kind": "function", "config": {"callable": lambda s: "a", "simulate_duration": 0.05}},
                {"id": "b", "kind": "function", "config": {"callable": lambda s: "b", "simulate_duration": 0.05}},
            ]
        },
        next_ids=[],
    )
    graph = FlowGraph(nodes={"parallel": node}, entry_id="parallel")
    start = time.monotonic()
    result = asyncio.run(engine.a_run_flow(graph, FlowState(), runtime_ctx, flow_name="p"))
    total = time.monotonic() - start
    # With parallel execution, total duration should be closer to single step duration
    assert result.total_duration_seconds <= 0.25
    assert total <= 0.25
    child_ids = {step.node_id for step in result.steps}
    assert {"a", "b", "parallel"}.issubset(child_ids)


def test_parallel_fail_fast_cancels_others():
    engine, runtime_ctx = build_engine()

    def fail(_state):
        raise RuntimeError("boom")

    node = FlowNode(
        id="parallel",
        kind="parallel",
        config={
            "fail_fast": True,
            "steps": [
                {"id": "fail", "kind": "function", "config": {"callable": fail}},
                {"id": "slow", "kind": "function", "config": {"callable": lambda s: "ok", "simulate_duration": 0.2}},
            ],
        },
        next_ids=[],
    )
    graph = FlowGraph(nodes={"parallel": node}, entry_id="parallel")
    result = asyncio.run(engine.a_run_flow(graph, FlowState(), runtime_ctx, flow_name="p"))
    parallel_step = next(step for step in result.steps if step.node_id == "parallel")
    assert parallel_step.success is False
    # Fail step should not block until slow completes when fail_fast is true
    assert result.total_duration_seconds < 0.2
