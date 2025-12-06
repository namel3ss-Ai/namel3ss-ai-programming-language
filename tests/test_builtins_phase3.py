import uuid
from datetime import datetime, date

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


def test_string_builtins():
    source = (
        'flow "strings":\n'
        '  step "s":\n'
        '    let name be "  Disan  "\n'
        '    let trimmed be trim of name\n'
        '    let lower be lowercase(name)\n'
        '    let text be "foo foo"\n'
        '    let replaced be replace "foo" with "bar" in text\n'
        '    let parts be split text by " "\n'
        '    let joined be join parts with "-"\n'
        '    let slug be slugify of "Hello World!"\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-strings")
    result = engine.run_flow(ir_prog.flows["strings"], ctx)
    assert not result.errors
    assert ctx.variables["trimmed"] == "Disan"
    assert ctx.variables["lower"] == "  disan  "
    assert ctx.variables["replaced"] == "bar bar"
    assert ctx.variables["joined"] == "foo-foo"
    assert ctx.variables["slug"] == "hello-world"
    assert tools.calls[0].get("message") == "hello-world"


def test_numeric_builtins_and_round_abs():
    source = (
        'flow "numbers":\n'
        '  step "s":\n'
        '    let scores be [12, 4, 9, 10]\n'
        '    let minimum be minimum of scores\n'
        '    let maximum be max(scores)\n'
        '    let average be mean of scores\n'
        '    let rounded be round average to 1\n'
        '    let absolute be absolute value of -5\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-numbers")
    result = engine.run_flow(ir_prog.flows["numbers"], ctx)
    assert not result.errors
    assert ctx.variables["minimum"] == 4
    assert ctx.variables["maximum"] == 12
    assert ctx.variables["rounded"] == 8.8
    assert ctx.variables["absolute"] == 5
    assert tools.calls[0].get("message") == 5


def test_any_all_boolean_helpers():
    source = (
        'flow "bools":\n'
        '  step "s":\n'
        '    let scores be [1, 2, 3]\n'
        '    let any_high be any score in scores where score > 2\n'
        '    let all_high be all score in scores where score > 0\n'
        '    let flags be [true, false, true]\n'
        '    let has_true be any(flags, where: item)\n'
        '    let all_true be all(flags, where: item)\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-bools")
    result = engine.run_flow(ir_prog.flows["bools"], ctx)
    assert not result.errors
    assert ctx.variables["any_high"] is True
    assert ctx.variables["all_high"] is True
    assert ctx.variables["has_true"] is True
    assert ctx.variables["all_true"] is False
    assert tools.calls[0].get("message") is False


def test_time_and_random_builtins():
    source = (
        'flow "time":\n'
        '  step "s":\n'
        '    let now be current timestamp\n'
        '    let today be current date\n'
        '    let rid be random uuid\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-time")
    result = engine.run_flow(ir_prog.flows["time"], ctx)
    assert not result.errors
    assert datetime.fromisoformat(ctx.variables["now"])
    assert date.fromisoformat(ctx.variables["today"])
    assert uuid.UUID(ctx.variables["rid"])
    assert tools.calls[0].get("message")


def test_join_non_list_errors():
    source = (
        'flow "errors":\n'
        '  step "s":\n'
        '    let sep be ", "\n'
        '    let bad_join be join 5 with sep\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-errors1")
    result = engine.run_flow(ir_prog.flows["errors"], ctx)
    assert result.errors
    assert any("N3-4001" in err.error or "join" in err.error for err in result.errors)


def test_join_non_string_items_errors():
    source = (
        'flow "errors":\n'
        '  step "s":\n'
        '    let items be [1, 2]\n'
        '    let bad_strings be join items with ", "\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-errors2")
    result = engine.run_flow(ir_prog.flows["errors"], ctx)
    assert result.errors
    assert any("N3-4001" in err.error or "join" in err.error for err in result.errors)


def test_aggregate_non_list_errors():
    source = (
        'flow "errors":\n'
        '  step "s":\n'
        '    let bad_min be minimum of 5\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-errors3")
    result = engine.run_flow(ir_prog.flows["errors"], ctx)
    assert result.errors
    assert any("N3-4100" in err.error or "aggregate" in err.error for err in result.errors)


def test_any_predicate_must_be_boolean():
    source = (
        'flow "errors":\n'
        '  step "s":\n'
        '    let bad_pred be any x in [1, 2] where "oops"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-errors4")
    result = engine.run_flow(ir_prog.flows["errors"], ctx)
    assert result.errors
    assert any("N3-4201" in err.error or "predicate" in err.error for err in result.errors)
