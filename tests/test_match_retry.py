from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir, IRProgram
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext


def _make_engine(ir_prog: IRProgram, fail_times: int = 0):
    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyTool:
        def __init__(self, calls):
            self.calls = calls
            self.remaining = fail_times

        def run(self, **kwargs):
            self.calls.append(kwargs)
            if self.remaining > 0:
                self.remaining -= 1
                return {"error": "fail"}
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


def test_match_literal_and_otherwise():
    source = (
        'flow "m":\n'
        '  step "s":\n'
        '    let intent be "billing"\n'
        '    match intent:\n'
        '      when "technical":\n'
        '        do agent "tech"\n'
        '      when "billing":\n'
        '        do agent "bill"\n'
        '      otherwise:\n'
        '        do agent "fallback"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, agents = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-match1")
    result = engine.run_flow(ir_prog.flows["m"], ctx)
    assert not result.errors
    assert agents.calls == ["bill"]


def test_match_success_and_error_patterns():
    source = (
        'flow "m":\n'
        '  step "s":\n'
        '    let result be { error: "oops" }\n'
        '    match result:\n'
        '      when success as value:\n'
        '        do agent "handle_success"\n'
        '      when error as err:\n'
        '        do agent "handle_error"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, agents = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-match2")
    result = engine.run_flow(ir_prog.flows["m"], ctx)
    assert not result.errors
    assert agents.calls == ["handle_error"]


def test_match_comparison_condition():
    source = (
        'flow "m":\n'
        '  step "s":\n'
        '    let score be 0.6\n'
        '    match score:\n'
        '      when score is less than 0.5:\n'
        '        do agent "low"\n'
        '      when score is at least 0.5 and score is less than 0.8:\n'
        '        do agent "mid"\n'
        '      otherwise:\n'
        '        do agent "high"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, agents = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-match3")
    result = engine.run_flow(ir_prog.flows["m"], ctx)
    assert not result.errors
    assert agents.calls == ["mid"]


def test_retry_with_backoff():
    source = (
        'flow "r":\n'
        '  step "s":\n'
        '    retry up to 3 times with backoff:\n'
        '      do tool "flaky"\n'
        '    do agent "done"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, agents = _make_engine(ir_prog, fail_times=2)
    ctx = ExecutionContext(app_name="test", request_id="req-retry")
    result = engine.run_flow(ir_prog.flows["r"], ctx)
    assert not result.errors
    # tool should have been called 3 times (2 failures, 1 success)
    assert len(tools.calls) == 3
    assert agents.calls == ["done"]


def test_retry_invalid_count_errors():
    source = (
        'flow "r":\n'
        '  step "s":\n'
        '    retry up to "oops" times:\n'
        '      do tool "flaky"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-retry-bad")
    result = engine.run_flow(ir_prog.flows["r"], ctx)
    assert result.errors

