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
    # Ensure the flows package is importable in this test environment
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
    ctx = ExecutionContext(app_name="test", request_id="req-records-v2", tool_registry=tool_registry, metrics=metrics)
    return engine, ctx


def _run_flow(source: str):
    program = ast_to_ir(parse_source(source))
    engine, ctx = _make_engine(program)
    flow = next(iter(program.flows.values()))
    return engine.run_flow(flow, ctx)


def test_let_destructuring_binds_fields():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let user be { name: "Alice", email: "alice@example.com" }\n'
        "    let { name, email } be user\n"
    )
    result = _run_flow(source)
    assert result.errors == []
    assert result.state
    assert result.state.data.get("name") == "Alice"
    assert result.state.data.get("email") == "alice@example.com"


def test_loop_destructuring_over_records():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let top_customers be [{ name: "Alice", total: 100 }, { name: "Bob", total: 50 }]\n'
        "    let sum_total be 0\n"
        "    let last_name be \"\"\n"
        "    repeat for each { name, total } in top_customers:\n"
        "      set sum_total be sum_total + total\n"
        "      set last_name be name\n"
    )
    result = _run_flow(source)
    assert result.errors == []
    assert result.state
    assert result.state.data.get("sum_total") == 150
    assert result.state.data.get("last_name") == "Bob"


def test_safe_get_with_default():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let user be { name: "Alice" }\n'
        '    let email be get user.email otherwise "unknown"\n'
    )
    result = _run_flow(source)
    assert result.errors == []
    assert result.state
    assert result.state.data.get("email") == "unknown"


def test_has_key_on_record():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let user be { name: "Alice" }\n'
        '    let has_email be has key "email" on user\n'
        '    let has_name be has key "name" on user\n'
    )
    result = _run_flow(source)
    assert result.errors == []
    assert result.state
    assert result.state.data.get("has_email") is False
    assert result.state.data.get("has_name") is True


def test_missing_field_access_has_diagnostics():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let user be { name: "Alice" }\n'
        "    let email be user.emial\n"
    )
    result = _run_flow(source)
    assert result.errors
    message = result.errors[0].error
    assert "emial" in message
    assert "Available fields" in message
    assert "get" in message and "otherwise" in message


def test_missing_field_in_destructuring_has_diagnostics():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let user be { name: "Alice" }\n'
        "    let { name, email } be user\n"
    )
    result = _run_flow(source)
    assert result.errors
    message = result.errors[0].error
    assert "email" in message
    assert "Available fields" in message
    assert "get" in message and "otherwise" in message
