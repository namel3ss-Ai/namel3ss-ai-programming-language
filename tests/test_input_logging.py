import pytest

from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir, IRProgram
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext


def _make_engine(ir_prog: IRProgram):
    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyTool:
        def __init__(self, calls):
            self.calls = calls

        def run(self, **kwargs):
            self.calls.append(kwargs)
            return {"ok": True}

    class DummyToolRegistry:
        def __init__(self):
            self.calls = []
            self.tool = DummyTool(self.calls)

        def get(self, name):
            return self.tool

    class DummyAgentRunner:
        def __init__(self):
            self.calls = []

        def run(self, name, context):
            self.calls.append(name)
            return {"agent": name}

    tool_registry = DummyToolRegistry()
    runner = DummyAgentRunner()
    engine = FlowEngine(
        program=ir_prog,
        model_registry=DummyModelRegistry(),
        tool_registry=tool_registry,
        agent_runner=runner,
        router=DummyRouter(),
        metrics=None,
        secrets=None,
    )
    return engine, tool_registry, runner


def test_ask_user_with_answer():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        '    ask user for "Email" as email\n'
        '    do agent "done"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, agents = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-ask1", metadata={"inputs": {"email": "a@example.com"}})
    result = engine.run_flow(ir_prog.flows["f"], ctx)
    assert not result.errors
    assert agents.calls == ["done"]
    assert result.state and result.state.variables and result.state.variables.resolve("email") == "a@example.com"


def test_ask_user_requests_input_when_missing():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        '    ask user for "Email" as email\n'
        '    do agent "done"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, agents = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-ask2", metadata={})
    result = engine.run_flow(ir_prog.flows["f"], ctx)
    assert not result.errors
    assert agents.calls == []
    assert result.state
    assert result.state.context.get("__awaiting_input__")
    assert result.state.inputs and result.state.inputs[0]["name"] == "email"


def test_form_collects_values():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        '    form "Signup" as signup:\n'
        '      field "Name" as name\n'
        '      field "Age" as age\n'
        '    do agent "done"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, agents = _make_engine(ir_prog)
    ctx = ExecutionContext(
        app_name="test",
        request_id="req-form",
        metadata={"inputs": {"signup": {"name": "Alice", "age": 30}}},
    )
    result = engine.run_flow(ir_prog.flows["f"], ctx)
    assert not result.errors
    assert agents.calls == ["done"]
    assert result.state
    assert result.state.data.get("signup") == {"name": "Alice", "age": 30}


def test_logging_notes_and_checkpoints_are_recorded():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        '    log info "Starting" with { status: "begin" }\n'
        '    note "midway"\n'
        '    checkpoint "after_midway"\n'
        '    do agent "done"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, agents = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-log")
    result = engine.run_flow(ir_prog.flows["f"], ctx)
    assert not result.errors
    assert agents.calls == ["done"]
    assert result.state
    assert result.state.logs and result.state.logs[0]["level"] == "info"
    assert result.state.notes and result.state.notes[0]["message"] == "midway"
    assert result.state.checkpoints and result.state.checkpoints[0]["label"] == "after_midway"


def test_invalid_validation_rule_errors():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        '    ask user for "X" as x\n'
        '      must be around 5\n'
    )
    with pytest.raises(Exception):
        ast_to_ir(parse_source(source))


def test_invalid_log_level_errors():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        '    log verbose "Nope"\n'
    )
    with pytest.raises(Exception):
        ast_to_ir(parse_source(source))
