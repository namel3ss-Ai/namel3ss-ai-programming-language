import pytest

from namel3ss import ast_nodes
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
        def __init__(self, calls):
            self.calls = calls

        def run(self, **kwargs):
            self.calls.append(kwargs)
            return {"tool": "echo", "args": kwargs}

    class DummyToolRegistry:
        def __init__(self):
            self.calls = []

        def get(self, name):
            return DummyTool(self.calls)

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


def test_list_builtins_and_sum():
    source = (
        'flow "lists":\n'
        '  step "s":\n'
        '    let xs be [1, 2, 3]\n'
        '    let l be length of xs\n'
        '    let r be reverse of xs\n'
        '    let s be sum(xs)\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-builtin")
    result = engine.run_flow(ir_prog.flows["lists"], ctx)
    assert not result.errors
    assert tools.calls[0].get("message") == 6


def test_filter_and_map_english_and_functional():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        '    let xs be [1, 2, 3]\n'
        '    let highs be all xs where item > 1\n'
        '    let doubled be map(xs, to: item * 2)\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-filter")
    result = engine.run_flow(ir_prog.flows["f"], ctx)
    assert not result.errors
    assert tools.calls[0].get("message") == [2, 4, 6]
    assert ctx.variables["highs"] == [2, 3]


def test_english_map_with_record_field_access():
    source = (
        'flow "map":\n'
        '  step "s":\n'
        '    let users be [{ email: "a@example.com" }, { email: "b@example.com" }]\n'
        '    let emails be all user.email from users\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-map")
    result = engine.run_flow(ir_prog.flows["map"], ctx)
    assert not result.errors
    assert ctx.variables["emails"] == ["a@example.com", "b@example.com"]
    assert tools.calls[0].get("message") == ["a@example.com", "b@example.com"]


def test_record_literal_and_field_access():
    source = (
        'flow "records":\n'
        '  step "s":\n'
        '    let user be { name: "Alice", age: 30 }\n'
        '    let n be user.name\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-record")
    engine.run_flow(ir_prog.flows["records"], ctx)
    assert tools.calls[0].get("message") == "Alice"


def test_for_each_loop_accumulates():
    source = (
        'flow "loop":\n'
        '  step "s":\n'
        '    let xs be [1, 2, 3]\n'
        '    let total be 0\n'
        '    repeat for each item in xs:\n'
        '      set total to total + item\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-loop")
    engine.run_flow(ir_prog.flows["loop"], ctx)
    assert tools.calls[0].get("message") == 6


def test_repeat_up_to_loop():
    source = (
        'flow "repeat":\n'
        '  step "s":\n'
        '    let count be 0\n'
        '    repeat up to 3 times:\n'
        '      set count to count + 1\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-repeat")
    engine.run_flow(ir_prog.flows["repeat"], ctx)
    assert tools.calls[0].get("message") == 3


def test_invalid_for_each_type_errors():
    source = (
        'flow "bad":\n'
        '  step "s":\n'
        '    let total be 0\n'
        '    repeat for each item in 5:\n'
        '      set total to total + item\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-bad-loop")
    result = engine.run_flow(ir_prog.flows["bad"], ctx)
    assert result.errors
    assert any("for-each loop" in err.error for err in result.errors)
