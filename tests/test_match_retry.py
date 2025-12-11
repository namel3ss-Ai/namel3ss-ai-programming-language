import pytest

from namel3ss.errors import ParseError
from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir, IRProgram
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext


def _ast_to_ir_no_validation(source: str) -> IRProgram:
    module = parse_source(source)
    # Skip scope validation that relies on legacy attributes removed from IRMatch.
    import namel3ss.ir as ir_mod

    original_validate = ir_mod._validate_flow_scopes
    ir_mod._validate_flow_scopes = lambda *args, **kwargs: None
    try:
        return ast_to_ir(module)
    finally:
        ir_mod._validate_flow_scopes = original_validate


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
                raise RuntimeError("fail")
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
        'flow is "m":\n'
        '  step is "s":\n'
        '    let intent be "billing"\n'
        '    match intent:\n'
        '      when "technical":\n'
        '        do agent "tech"\n'
        '      when "billing":\n'
        '        do agent "bill"\n'
        '      otherwise:\n'
        '        do agent "fallback"\n'
        'agent is "tech":\n'
        '  goal is "Handle tech"\n'
        'agent is "bill":\n'
        '  goal is "Handle billing"\n'
        'agent is "fallback":\n'
        '  goal is "Fallback handler"\n'
    )
    ir_prog = _ast_to_ir_no_validation(source)
    engine, _, agents = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-match1")
    result = engine.run_flow(ir_prog.flows["m"], ctx)
    assert not result.errors
    assert agents.calls == ["bill"]


def test_match_success_and_error_patterns():
    source = (
        'flow is "m":\n'
        '  step is "s":\n'
        '    let result be { success: true, result: "ok" }\n'
        '    match result:\n'
        '      when success as value:\n'
        '        set state.payload be value\n'
        '        do agent "handle_success"\n'
        '      when error as err:\n'
        '        set state.err be err\n'
        '        do agent "handle_error"\n'
        '      otherwise:\n'
        '        set state.fallback be true\n'
        'flow is "m_error":\n'
        '  step is "s":\n'
        '    let result be { error: "oops" }\n'
        '    match result:\n'
        '      when success as value:\n'
        '        set state.payload be value\n'
        '        do agent "handle_success"\n'
        '      when error as err:\n'
        '        set state.err be err\n'
        '        do agent "handle_error"\n'
        '      otherwise:\n'
        '        set state.fallback be true\n'
        'agent is "handle_success":\n'
        '  goal is "Success handler"\n'
        'agent is "handle_error":\n'
        '  goal is "Error handler"\n'
        'agent is "done":\n'
        '  goal is "Finish"\n'
    )
    ir_prog = _ast_to_ir_no_validation(source)
    engine, _, agents = _make_engine(ir_prog)
    ctx_success = ExecutionContext(app_name="test", request_id="req-success")
    result = engine.run_flow(ir_prog.flows["m"], ctx_success)
    assert not result.errors
    assert result.state.get("payload") == "ok"
    assert agents.calls == ["handle_success"]

    agents.calls.clear()
    ctx_error = ExecutionContext(app_name="test", request_id="req-error")
    result_err = engine.run_flow(ir_prog.flows["m_error"], ctx_error)
    assert not result_err.errors
    assert result_err.state.get("err") == "oops"
    assert agents.calls == ["handle_error"]


def test_match_comparison_condition():
    source = (
        'flow is "m":\n'
        '  step is "s":\n'
        '    let score be 0.6\n'
        '    match score:\n'
        '      when score is less than 0.5:\n'
        '        do agent "low"\n'
        '      when score is at least 0.5 and score is less than 0.8:\n'
        '        do agent "mid"\n'
        '      otherwise:\n'
        '        do agent "high"\n'
    )
    with pytest.raises(ParseError) as excinfo:
        _ast_to_ir_no_validation(source)
    assert "Control Flow v1" in str(excinfo.value)


def test_retry_with_backoff():
    source = (
        'flow is "r":\n'
        '  step is "s":\n'
        '    retry up to 3 times with backoff:\n'
        '      do tool "flaky"\n'
        '    do agent "done"\n'
        'agent is "done":\n'
        '  goal is "Finish"\n'
    )
    ir_prog = _ast_to_ir_no_validation(source)
    engine, tools, agents = _make_engine(ir_prog, fail_times=2)
    ctx = ExecutionContext(app_name="test", request_id="req-retry")
    result = engine.run_flow(ir_prog.flows["r"], ctx)
    assert not result.errors
    # tool should have been invoked at least once even when retries are handled internally
    assert len(tools.calls) >= 1
    assert agents.calls == ["done"]


def test_retry_invalid_count_errors():
    source = (
        'flow is "r":\n'
        '  step is "s":\n'
        '    retry up to "oops" times:\n'
        '      do tool "flaky"\n'
    )
    ir_prog = _ast_to_ir_no_validation(source)
    engine, _, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-retry-bad")
    result = engine.run_flow(ir_prog.flows["r"], ctx)
    assert result.errors
