from dataclasses import dataclass

from namel3ss.ast_nodes import FlowDecl, FlowStepDecl
from namel3ss.ir import ast_to_ir, IRAgent, IRProgram
from namel3ss.parser import parse_source
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

    @dataclass
    class AgentResult:
        name: str
        output: str

    class StubAgentRunner:
        def __init__(self):
            self.calls = []

        def run(self, name, context):
            self.calls.append(name)
            return AgentResult(name=name, output="ok")

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


def test_parse_flow_with_if_chain():
    module = parse_source(
        'flow "support_flow":\n'
        '  step "route":\n'
        '    if result.category is "billing":\n'
        '      do agent "billing_agent"\n'
        '    otherwise if result.category is "technical":\n'
        '      do agent "tech_agent"\n'
        '    otherwise:\n'
        '      do agent "general_agent"\n'
    )
    flow = next(d for d in module.declarations if isinstance(d, FlowDecl))
    step = flow.steps[0]
    assert isinstance(step, FlowStepDecl)
    assert step.conditional_branches is not None
    assert len(step.conditional_branches) == 3
    assert step.conditional_branches[0].condition is not None
    assert step.conditional_branches[2].condition is None  # otherwise


def test_runtime_condition_branch_selection_and_trace():
    source = (
        'agent "billing_agent":\n'
        '  the goal is "billing"\n'
        '  the personality is "direct"\n'
        'agent "general_agent":\n'
        '  the goal is "general"\n'
        '  the personality is "helpful"\n'
        'flow "support_flow":\n'
        '  step "route":\n'
        '    if result.category is "billing":\n'
        '      do agent "billing_agent"\n'
        '    otherwise:\n'
        '      do agent "general_agent"\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    tracer = Tracer()
    ctx = ExecutionContext(app_name="test", request_id="req-1", tracer=tracer)
    engine = _make_engine(ir_prog)
    flow = ir_prog.flows["support_flow"]
    result = engine.run_flow(flow, ctx, initial_state={"result": {"category": "billing"}})
    # Agent runner should have been called with billing_agent
    assert engine._agent_runner_stub.calls == ["billing_agent"]
    # Trace should include condition evaluation event
    assert any(
        evt.get("event") == "flow.condition.eval" and evt.get("result") is True
        for evt in (tracer.last_trace.flows[0].events if tracer.last_trace and tracer.last_trace.flows else [])
    )
    # State should include outputs
    assert result.state.get("last_output") is not None


def test_when_runs_single_branch():
    source = (
        'agent "vip_agent":\n'
        '  the goal is "vip"\n'
        '  the personality is "polite"\n'
        'flow "vip_flow":\n'
        '  step "maybe_escalate":\n'
        '    when user.is_vip is "true":\n'
        '      do agent "vip_agent"\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    tracer = Tracer()
    ctx = ExecutionContext(app_name="test", request_id="req-2", tracer=tracer)
    engine = _make_engine(ir_prog)
    flow = ir_prog.flows["vip_flow"]
    engine.run_flow(flow, ctx, initial_state={"user": {"is_vip": "true"}})
    assert engine._agent_runner_stub.calls == ["vip_agent"]
