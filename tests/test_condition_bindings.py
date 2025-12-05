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
            self.last_ctx = None

        def run(self, name, context):
            self.calls.append(name)
            self.last_ctx = context
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


def test_parser_allows_binding_variants():
    module = parse_source(
        'flow "f":\n'
        '  step "s":\n'
        '    if result.category is "billing" as cat:\n'
        '      do agent "billing"\n'
        '    otherwise if result.category is "tech" as t:\n'
        '      do agent "tech_agent"\n'
        '    otherwise:\n'
        '      do agent "other"\n'
        '  step "w":\n'
        '    when score > 0.8 as high:\n'
        '      do agent "vip"\n'
        '  step "u":\n'
        '    unless flag is "off" as fl:\n'
        '      do agent "on"\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    assert flow.steps[0].conditional_branches[0].binding == "cat"
    assert flow.steps[0].conditional_branches[1].binding == "t"
    assert flow.steps[1].conditional_branches[0].binding == "high"
    assert flow.steps[2].conditional_branches[0].binding == "fl"


def test_parser_binding_errors():
    with pytest.raises(Exception):
        parse_source(
            'flow "f":\n'
            '  step "s":\n'
            '    if result is "x" as:\n'
            '      do agent "a"\n'
        )
    with pytest.raises(Exception):
        parse_source(
            'flow "f":\n'
            '  step "s":\n'
            '    when result is "x" as 123:\n'
            '      do agent "a"\n'
        )
    with pytest.raises(Exception):
        parse_source(
            'flow "f":\n'
            '  step "s":\n'
            '    if result is "x" as a as b:\n'
            '      do agent "a"\n'
        )


def test_flow_runtime_binding_and_trace():
    source = (
        'agent "billing":\n'
        '  the goal is "g"\n'
        '  the personality is "p"\n'
        'flow "f":\n'
        '  step "s":\n'
        '    if result.category is "billing" as cat:\n'
        '      do agent "billing"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    tracer = Tracer()
    engine = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="app", request_id="r1", tracer=tracer)
    flow = ir_prog.flows["f"]
    engine.run_flow(flow, ctx, initial_state={"result": {"category": "billing"}})
    assert engine._runner_stub.calls == ["billing"]
    # binding should not leak after block
    assert "cat" not in engine._runner_stub.last_ctx.metadata
    events = tracer.last_trace.flows[0].events if tracer.last_trace and tracer.last_trace.flows else []
    assert any(evt.get("binding", {}).get("name") == "cat" for evt in events)


def test_agent_runtime_binding():
    source = (
        'agent "triage_agent":\n'
        '  if user.score > 0.8 as high:\n'
        '    do tool "send_alert" with message:\n'
        '      "high"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    tools_called = []

    class StubTool:
        def __init__(self, name):
            self.name = name

        def run(self, message: str = "", **kwargs):
            tools_called.append({"name": self.name, "message": message})
            return {"tool": self.name, "message": message}

    class StubToolRegistry:
        def __init__(self):
            self.t = StubTool("send_alert")

        def get(self, name):
            return self.t if name == "send_alert" else None

        def list_names(self):
            return ["send_alert"]

    from namel3ss.agent.engine import AgentRunner

    tracer = Tracer()
    ctx = ExecutionContext(app_name="app", request_id="r2", tracer=tracer, metadata={"user": {"score": 0.9}})
    runner = AgentRunner(program=ir_prog, model_registry=None, tool_registry=StubToolRegistry(), router=None, evaluator=None)
    runner.run("triage_agent", ctx)
    assert tools_called, "tool should run when condition true"
    # binding should not persist
    assert "high" not in ctx.metadata
    agent_trace = tracer.last_trace.pages[0].agents[0] if tracer.last_trace and tracer.last_trace.pages else None
    assert agent_trace is not None
    assert any(evt.get("binding", {}).get("name") == "high" for evt in agent_trace.events)
