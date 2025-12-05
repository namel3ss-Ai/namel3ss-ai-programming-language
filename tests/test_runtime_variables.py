import pytest

from namel3ss.errors import Namel3ssError
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
        def __init__(self, name: str, calls: list[dict]):
            self.name = name
            self.calls = calls

        def run(self, **kwargs):
            self.calls.append({"name": self.name, **kwargs})
            return {"tool": self.name, "args": kwargs}

    class DummyToolRegistry:
        def __init__(self):
            self.calls: list[dict] = []

        def get(self, name):
            return DummyTool(name, self.calls)

    class DummyAgentRunner:
        def __init__(self):
            self.calls: list[str] = []

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
    engine._tool_calls = tool_registry.calls
    engine._agent_calls = runner.calls
    return engine, tool_registry, runner


def test_let_set_flow_execution():
    source = (
        'flow "calc":\n'
        '  step "compute":\n'
        '    let base = 2\n'
        '    set base to base * 3\n'
        '    if base > 5:\n'
        '      do tool "echo"\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-vars")
    engine.run_flow(ir_prog.flows["calc"], ctx)
    assert len(tools.calls) == 1
    assert tools.calls[0].get("message") == 6


def test_variable_across_steps():
    source = (
        'flow "use_var":\n'
        '  step "define":\n'
        '    let a = 2\n'
        '  step "check":\n'
        '    if a >= 2:\n'
        '      do tool "echo"\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-vars2")
    engine.run_flow(ir_prog.flows["use_var"], ctx)
    assert len(tools.calls) == 1


def test_duplicate_variable_errors():
    source = (
        'flow "dup":\n'
        '  step "s":\n'
        '    let x = 1\n'
        '    let x = 2\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    engine, _, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-dup")
    result = engine.run_flow(ir_prog.flows["dup"], ctx)
    assert result.errors
    assert any("already defined" in err.error for err in result.errors)


def test_set_undefined_errors():
    source = (
        'flow "undef":\n'
        '  step "s":\n'
        '    set x to 1\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    engine, _, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-undef")
    result = engine.run_flow(ir_prog.flows["undef"], ctx)
    assert result.errors
    assert any("not defined" in err.error for err in result.errors)


def test_type_mismatch_errors():
    source = (
        'flow "bad":\n'
        '  step "s":\n'
        '    let x = "hi"\n'
        '    set x to x + 1\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    engine, _, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-type")
    result = engine.run_flow(ir_prog.flows["bad"], ctx)
    assert result.errors
    assert any("non-numeric" in err.error for err in result.errors)


def test_divide_by_zero_errors():
    source = (
        'flow "div":\n'
        '  step "s":\n'
        '    let x = 1\n'
        '    set x to x / 0\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    engine, _, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-div0")
    result = engine.run_flow(ir_prog.flows["div"], ctx)
    assert result.errors
    assert any("divide by zero" in err.error.lower() for err in result.errors)


def test_boolean_logic_and_parentheses():
    source = (
        'flow "logic":\n'
        '  step "s":\n'
        '    let a = 1\n'
        '    if a > 0 and not false:\n'
        '      do tool "echo"\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-logic")
    engine.run_flow(ir_prog.flows["logic"], ctx)
    assert len(tools.calls) == 1
