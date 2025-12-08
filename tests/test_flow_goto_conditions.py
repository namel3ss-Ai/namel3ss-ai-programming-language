import pytest

from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir, IRProgram
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext
from namel3ss.obs.tracer import Tracer
from namel3ss.errors import ParseError


def _make_engine(ir_prog: IRProgram):
    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyTool:
        def __init__(self, name: str, calls: list[str]):
            self.name = name
            self.calls = calls

        def run(self, **kwargs):
            self.calls.append(self.name)
            return {"tool": self.name, "args": kwargs}

        def __call__(self, payload):
            if isinstance(payload, dict):
                return self.run(**payload)
            return self.run()

    class DummyToolRegistry:
        def __init__(self):
            self.calls: list[str] = []

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
    return engine


def test_parse_goto_flow_in_step():
    module = parse_source(
        'flow "start":\n'
        '  step "jump":\n'
        '    go to flow "end"\n'
    )
    flow = next(d for d in module.declarations if getattr(d, "name", "") == "start")
    step = flow.steps[0]
    assert step.kind == "goto_flow"
    assert step.target == "end"


def test_runtime_redirect_runs_target_flow():
    source = (
        'flow "start":\n'
        '  step "jump":\n'
        '    go to flow "end"\n'
'flow "end":\n'
'  step "done":\n'
'    kind "tool"\n'
'    tool "echo"\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    tracer = Tracer()
    ctx = ExecutionContext(app_name="test", request_id="req-goto-1", tracer=tracer)
    engine = _make_engine(ir_prog)
    result = engine.run_flow(ir_prog.flows["start"], ctx, initial_state={})
    # Redirect should have executed the end flow's step
    assert "echo" in engine._tool_calls
    assert result.redirect_to is None
    # Trace should include flow.goto event
    flow_events = tracer.last_trace.flows[0].events if tracer.last_trace and tracer.last_trace.flows else []
    assert any(evt.get("event") == "flow.goto" for evt in flow_events)


def test_conditional_redirect_branch_selection():
    source = (
        'flow "router":\n'
        '  step "route":\n'
        '    if result.category is "billing":\n'
        '      go to flow "billing_flow"\n'
        '    otherwise:\n'
        '      go to flow "fallback_flow"\n'
'flow "billing_flow":\n'
'  step "bill":\n'
'    kind "tool"\n'
'    tool "echo"\n'
'flow "fallback_flow":\n'
'  step "fb":\n'
'    kind "tool"\n'
'    tool "echo"\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    tracer = Tracer()
    ctx = ExecutionContext(app_name="test", request_id="req-goto-2", tracer=tracer)
    engine = _make_engine(ir_prog)
    engine.run_flow(ir_prog.flows["router"], ctx, initial_state={"result": {"category": "billing"}})
    assert engine._tool_calls.count("echo") == 1
    # After conditional redirect, the billing_flow should run
    flow_names = [f.flow_name for f in (tracer.last_trace.flows if tracer.last_trace else [])]
    assert "billing_flow" in flow_names
    goto_events = [evt for f in tracer.last_trace.flows for evt in f.events]
    assert any(evt.get("event") == "flow.goto" and evt.get("reason") == "conditional" for evt in goto_events)


def test_goto_requires_string_literal():
    with pytest.raises(ParseError):
        parse_source(
            'flow "start":\n'
            '  step "jump":\n'
            '    go to flow end\n'
        )
