from namel3ss import ast_nodes
from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir
from namel3ss.agent.engine import AgentRunner
from namel3ss.runtime.context import ExecutionContext
from namel3ss.obs.tracer import Tracer


class StubTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[dict] = []

    def run(self, message: str = "", **kwargs):
        self.calls.append({"message": message, **kwargs})
        return {"tool": self.name, "message": message}


class StubToolRegistry:
    def __init__(self, tools: dict[str, StubTool]) -> None:
        self.tools = tools

    def get(self, name: str):
        return self.tools.get(name)

    def list_names(self):
        return list(self.tools.keys())


class DummyRegistry:
    def __getattr__(self, item):
        raise AttributeError


def _make_runner(ir_prog):
    tools = {"lookup_invoice": StubTool("lookup_invoice"), "create_ticket": StubTool("create_ticket")}
    registry = StubToolRegistry(tools)
    runner = AgentRunner(
        program=ir_prog,
        model_registry=DummyRegistry(),
        tool_registry=registry,
        router=DummyRegistry(),
    )
    runner._tools = tools
    return runner


def test_parse_agent_when_block():
    module = parse_source(
        'agent "support_agent":\n'
        '  the goal is "Help."\n'
        '  when user_intent is "billing":\n'
        '    do tool "lookup_invoice"\n'
        '  otherwise:\n'
        '    do tool "create_ticket"\n'
    )
    agent = next(d for d in module.declarations if isinstance(d, ast_nodes.AgentDecl))
    assert agent.conditional_branches is not None
    assert len(agent.conditional_branches) == 2
    assert agent.conditional_branches[0].condition is not None
    assert agent.conditional_branches[1].condition is None


def test_agent_condition_runtime_branch_selection_and_trace():
    source = (
        'agent "support_agent":\n'
        '  the goal is "Help."\n'
        '  when user_intent is "billing":\n'
        '    do tool "lookup_invoice"\n'
        '  otherwise:\n'
        '    do tool "create_ticket"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    tracer = Tracer()
    ctx = ExecutionContext(app_name="app", request_id="r1", metadata={"user_intent": "billing"}, tracer=tracer)
    runner = _make_runner(ir_prog)
    result = runner.run("support_agent", ctx)
    assert runner._tools["lookup_invoice"].calls, "billing branch should run"
    # Trace should include agent condition evaluation
    agent_trace = tracer.last_trace.pages[0].agents[0] if tracer.last_trace and tracer.last_trace.pages else None
    assert agent_trace is not None
    assert any(evt.get("event") == "agent.condition.eval" for evt in agent_trace.events)
    assert "billing" in (result.summary or "")


def test_agent_condition_fallback_branch():
    source = (
        'agent "triage_agent":\n'
        '  the goal is "Route"\n'
        '  if user_intent is "billing":\n'
        '    do tool "lookup_invoice"\n'
        '  otherwise:\n'
        '    do tool "create_ticket"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    ctx = ExecutionContext(app_name="app", request_id="r2", metadata={"user_intent": "unknown"}, tracer=Tracer())
    runner = _make_runner(ir_prog)
    runner.run("triage_agent", ctx)
    assert runner._tools["create_ticket"].calls, "fallback branch should run when no match"
