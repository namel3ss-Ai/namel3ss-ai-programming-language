import pytest

from namel3ss import ast_nodes
from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext
from namel3ss.obs.tracer import Tracer


def _make_engine(ir_prog):
    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class StubAgentRunner:
        def __init__(self):
            self.calls = []

        def run(self, name, context):
            self.calls.append(name)
            return {"agent": name}

    class StubToolRegistry:
        def get(self, name):
            return None

    runner = StubAgentRunner()
    engine = FlowEngine(
        program=ir_prog,
        model_registry=DummyModelRegistry(),
        tool_registry=StubToolRegistry(),
        agent_runner=runner,
        router=DummyRouter(),
        metrics=None,
        secrets=None,
    )
    engine._runner_stub = runner
    return engine


def test_parse_pattern_in_condition():
    module = parse_source(
        'flow "f":\n'
        '  step "route":\n'
        '    if result matches { category: "billing", priority: high } as cat:\n'
        '      do agent "billing_handler"\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    branch = flow.steps[0].conditional_branches[0]
    assert isinstance(branch.condition, ast_nodes.PatternExpr)
    assert branch.binding == "cat"
    assert branch.condition.subject.name == "result"
    assert len(branch.condition.pairs) == 2


def test_pattern_runtime_match_and_binding_flow():
    source = (
        'agent "billing_handler":\n'
        '  the goal is "g"\n'
        '  the personality is "p"\n'
        'flow "f":\n'
        '  step "route":\n'
        '    if result matches { category: "billing", priority: "high" } as cat:\n'
        '      do agent "billing_handler"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    tracer = Tracer()
    engine = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="app", request_id="req", tracer=tracer)
    flow = ir_prog.flows["f"]
    engine.run_flow(flow, ctx, initial_state={"result": {"category": "billing", "priority": "high"}})
    assert engine._runner_stub.calls == ["billing_handler"]
    events = tracer.last_trace.flows[0].events if tracer.last_trace and tracer.last_trace.flows else []
    assert any(evt.get("event") == "condition.pattern.eval" and evt.get("result") is True for evt in events)


def test_pattern_runtime_no_match_skips():
    source = (
        'agent "handler":\n'
        '  the goal is "g"\n'
        '  the personality is "p"\n'
        'flow "f":\n'
        '  step "route":\n'
        '    if result matches { category: "billing" } as cat:\n'
        '      do agent "handler"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="app", request_id="req")
    flow = ir_prog.flows["f"]
    engine.run_flow(flow, ctx, initial_state={"result": {"category": "other"}})
    assert engine._runner_stub.calls == []


def test_pattern_agent_runtime_and_trace():
    source = (
        'agent "triage":\n'
        '  if user matches { status: "vip", score: score >= threshold } as prof:\n'
        '    do tool "send_alert" with message:\n'
        '      "vip"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    tools_called = []

    class StubTool:
        def __init__(self, name):
            self.name = name

        def run(self, message: str = "", **kwargs):
            tools_called.append({"name": self.name, "message": message})
            return {"tool": self.name}

    class StubToolRegistry:
        def __init__(self):
            self.t = StubTool("send_alert")

        def get(self, name):
            return self.t if name == "send_alert" else None

        def list_names(self):
            return ["send_alert"]

    from namel3ss.agent.engine import AgentRunner

    tracer = Tracer()
    ctx = ExecutionContext(
        app_name="app",
        request_id="r2",
        tracer=tracer,
        metadata={"user": {"status": "vip", "score": 10}, "threshold": 5},
    )
    runner = AgentRunner(program=ir_prog, model_registry=None, tool_registry=StubToolRegistry(), router=None, evaluator=None)
    runner.run("triage", ctx)
    assert tools_called, "tool should run when pattern matches"
    agent_trace = tracer.last_trace.pages[0].agents[0] if tracer.last_trace and tracer.last_trace.pages else None
    assert agent_trace is not None
    assert any(evt.get("event") == "agent.condition.pattern.eval" for evt in agent_trace.events)


def test_pattern_invalid_nested_errors():
    with pytest.raises(Exception):
        parse_source(
            'flow "f":\n'
            '  step "s":\n'
            '    if result matches { nested: { x: 1 } }:\n'
            '      do agent "a"\n'
        )
