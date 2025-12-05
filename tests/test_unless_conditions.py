import pytest

from namel3ss import ast_nodes
from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir, IRProgram
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext
from namel3ss.obs.tracer import Tracer


def _make_engine(ir_prog: IRProgram) -> FlowEngine:
    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyToolRegistry:
        def get(self, name):
            return None

    class StubAgentRunner:
        def __init__(self):
            self.calls = []

        def run(self, name, context):
            self.calls.append(name)
            return {"agent": name}

    runner = StubAgentRunner()
    engine = FlowEngine(
        program=ir_prog,
        model_registry=DummyModelRegistry(),
        tool_registry=DummyToolRegistry(),
        agent_runner=runner,
        router=DummyRouter(),
        metrics=None,
        secrets=None,
    )
    engine._agent_runner_stub = runner
    return engine


def test_parse_flow_unless_branch():
    module = parse_source(
        'flow "f":\n'
        '  step "s":\n'
        '    unless result.priority is "low":\n'
        '      do agent "handle"\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    step = flow.steps[0]
    assert step.conditional_branches is not None
    br = step.conditional_branches[0]
    assert br.label == "unless"
    assert isinstance(br.condition, ast_nodes.Expr)
    assert br.actions[0].target == "handle"


def test_parse_agent_unless_branch():
    module = parse_source(
        'agent "a":\n'
        '  unless user.is_new:\n'
        '    do tool "audit"\n'
    )
    agent = next(d for d in module.declarations if isinstance(d, ast_nodes.AgentDecl))
    assert agent.conditional_branches is not None
    assert agent.conditional_branches[0].label == "unless"


def test_unless_followed_by_otherwise_raises():
    with pytest.raises(Exception):
        parse_source(
            'flow "f":\n'
            '  step "s":\n'
            '    unless x is 1:\n'
            '      do agent "a"\n'
            '    otherwise:\n'
            '      do agent "b"\n'
        )


def test_unless_missing_expression_raises():
    with pytest.raises(Exception):
        parse_source(
            'flow "f":\n'
            '  step "s":\n'
            '    unless:\n'
            '      do agent "a"\n'
        )


def test_flow_unless_runtime_and_trace():
    source = (
        'agent "handle":\n'
        '  the goal is "g"\n'
        '  the personality is "p"\n'
        'flow "f":\n'
        '  step "s":\n'
        '    unless result.priority is "low":\n'
        '      do agent "handle"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    tracer = Tracer()
    engine = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="app", request_id="r1", tracer=tracer)
    flow = ir_prog.flows["f"]
    engine.run_flow(flow, ctx, initial_state={"result": {"priority": "high"}})
    # agent should run because condition false -> unless true
    assert engine._agent_runner_stub.calls == ["handle"]
    events = tracer.last_trace.flows[0].events if tracer.last_trace and tracer.last_trace.flows else []
    assert any(evt.get("event") == "flow.condition.eval" for evt in events)


def test_flow_unless_skips_when_condition_true():
    source = (
        'agent "handle":\n'
        '  the goal is "g"\n'
        '  the personality is "p"\n'
        'flow "f":\n'
        '  step "s":\n'
        '    unless result.priority is "low":\n'
        '      do agent "handle"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="app", request_id="r3")
    flow = ir_prog.flows["f"]
    engine.run_flow(flow, ctx, initial_state={"result": {"priority": "low"}})
    assert engine._agent_runner_stub.calls == []


def test_agent_unless_runtime():
    source = (
        'agent "review_agent":\n'
        '  unless ticket.status is "closed":\n'
        '    do tool "send_notification"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    tools_called = []

    class StubTool:
        def __init__(self, name):
            self.name = name

        def run(self, message: str = "", **kwargs):
            tools_called.append(self.name)
            return {"tool": self.name}

    class StubToolRegistry:
        def __init__(self):
            self.t = StubTool("send_notification")

        def get(self, name):
            return self.t if name == "send_notification" else None

        def list_names(self):
            return ["send_notification"]

    tracer = Tracer()
    ctx = ExecutionContext(app_name="app", request_id="r2", tracer=tracer, metadata={"ticket": {"status": "open"}})
    # Directly invoke agent runner path
    from namel3ss.agent.engine import AgentRunner

    registry = StubToolRegistry()
    agent_runner = AgentRunner(program=ir_prog, model_registry=None, tool_registry=registry, router=None, evaluator=None)
    agent_runner.run("review_agent", ctx)
    assert "send_notification" in tools_called
    tools_called.clear()
    ctx_closed = ExecutionContext(app_name="app", request_id="r3", tracer=Tracer(), metadata={"ticket": {"status": "closed"}})
    agent_runner.run("review_agent", ctx_closed)
    assert tools_called == []
