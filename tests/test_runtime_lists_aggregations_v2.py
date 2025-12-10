from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ir import IRProgram, ast_to_ir
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.parser import parse_source
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


def _make_engine(program: IRProgram):
    if "namel3ss.flows" not in sys.modules or not isinstance(sys.modules.get("namel3ss.flows"), types.ModuleType):
        flows_pkg = types.ModuleType("namel3ss.flows")
        flows_pkg.__path__ = [str(Path(__file__).resolve().parent.parent / "src" / "namel3ss" / "flows")]
        sys.modules["namel3ss.flows"] = flows_pkg
    FlowEngine = importlib.import_module("namel3ss.flows.engine").FlowEngine
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
    ctx = ExecutionContext(app_name="test", request_id="req-lists-v2", tool_registry=tool_registry, metrics=metrics)
    return engine, ctx


def _run_flow(source: str):
    program = ast_to_ir(parse_source(source))
    engine, ctx = _make_engine(program)
    flow = next(iter(program.flows.values()))
    return engine.run_flow(flow, ctx)


def test_basic_aggregates():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be [1, 2, 3]\n"
        "    let total be sum of xs\n"
        "    let avg be mean of xs\n"
        "    let min_v be minimum of xs\n"
        "    let max_v be maximum of xs\n"
        "    let cnt be count of xs\n"
    )
    result = _run_flow(source)
    assert result.errors == []
    state = result.state.data
    assert state.get("total") == 6
    assert state.get("avg") == 2
    assert state.get("min_v") == 1
    assert state.get("max_v") == 3
    assert state.get("cnt") == 3


def test_aggregate_errors():
    empty_mean = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be []\n"
        "    let avg be mean of xs\n"
    )
    result = _run_flow(empty_mean)
    assert result.errors
    assert "empty list" in result.errors[0].error

    non_numeric = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let xs be ["a", "b"]\n'
        "    let total be sum of xs\n"
    )
    result2 = _run_flow(non_numeric)
    assert result2.errors
    assert "list of numbers" in result2.errors[0].error


def test_list_helpers():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be [1, 2, 3]\n"
        "    let ys be append xs with 4\n"
        "    let zs be remove 2 from xs\n"
        "    let ins be insert 4 at 3 into xs\n"
    )
    result = _run_flow(source)
    assert result.errors == []
    state = result.state.data
    assert state.get("ys") == [1, 2, 3, 4]
    assert state.get("xs") == [1, 2, 3]
    assert state.get("zs") == [1, 3]
    assert state.get("ins") == [1, 2, 3, 4]


def test_insert_invalid_index():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be [1, 2]\n"
        "    let ys be insert 5 at -1 into xs\n"
    )
    result = _run_flow(source)
    assert result.errors
    assert "non-negative index" in result.errors[0].error


def test_group_by_aggregates():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let sales be [{ customer_id: "c1", amount: 10 }, { customer_id: "c1", amount: 20 }, { customer_id: "c2", amount: 5 }]:\n'
        "      group by row.customer_id:\n"
        "        let total_spent be sum of row.amount\n"
        "        let orders_count be count of rows\n"
        "        let avg_order be mean of row.amount\n"
    )
    result = _run_flow(source)
    assert result.errors == []
    summary = result.state.data.get("sales")
    assert isinstance(summary, list)
    assert {g.get("key") for g in summary} == {"c1", "c2"}
    c1 = next(g for g in summary if g.get("key") == "c1")
    c2 = next(g for g in summary if g.get("key") == "c2")
    assert c1["total_spent"] == 30
    assert c1["orders_count"] == 2
    assert c1["avg_order"] == 15
    assert c2["total_spent"] == 5
    assert c2["orders_count"] == 1
    assert c2["avg_order"] == 5
